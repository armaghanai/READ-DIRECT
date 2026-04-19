import pickle
import json
import csv
import os
import time
import spacy
import math
import struct
import numpy as np
from collections import defaultdict

class SearchEngine:
    def __init__(self):
        self.index_dir = r"d:\MyProjects\DigitalLibrary\books_data\index"
        self.lexicon_file = r"d:\MyProjects\DigitalLibrary\books_data\lexicon.csv"
        self.glove_path = r"d:\MyProjects\DigitalLibrary\embeddings\glove.6B.100d.bin"
        
        print("Initializing Search Engine... (Loading data into RAM)", flush=True)
        start_time = time.time()
        
        # 1. Load Lexicon
        self.lexicon = {}
        with open(self.lexicon_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.lexicon[row['word']] = int(row['word_id'])
        
        # 2. Load Stats
        with open(os.path.join(self.index_dir, "search_stats.json"), "r") as f:
            stats = json.load(f)
            self.avg_dl = stats['avg_dl']
            self.total_docs = stats['total_docs']
            
        # 3. Load IDF Values
        with open(os.path.join(self.index_dir, "idf_values.bin"), "rb") as f:
            self.idf_values = pickle.load(f)
            
        # 4. Load Doc Lengths
        with open(os.path.join(self.index_dir, "doc_lengths.bin"), "rb") as f:
            self.doc_lengths = pickle.load(f)
            
        # 5. Load Metadata Cache
        with open(os.path.join(self.index_dir, "metadata_cache.bin"), "rb") as f:
            self.metadata_cache = pickle.load(f)
            
        # 6. Load Autocomplete Trie
        with open(os.path.join(self.index_dir, "autocomplete_trie.bin"), "rb") as f:
            self.trie_root = pickle.load(f)

        # 7. Load Semantic Data
        self.doc_vectors = np.load(os.path.join(self.index_dir, "doc_vectors.npy"))
        with open(os.path.join(self.index_dir, "vector_isbns.bin"), "rb") as f:
            self.vector_isbns = pickle.load(f)
        
        # Mapping for fast vector lookup (ISBN -> Vector Index)
        self.isbn_to_vec_idx = {isbn: i for i, isbn in enumerate(self.vector_isbns)}

        # Load GloVe for query embedding (loading binary format)
        self.glove = {}
        with open(self.glove_path, 'rb') as f:
            header = f.read(8)
            word_count, dim = struct.unpack('ii', header)
            self.vector_dim = dim
            for _ in range(word_count):
                w_len = struct.unpack('i', f.read(4))[0]
                word = f.read(w_len).decode('utf-8', errors='ignore')
                vector = struct.unpack('f'*dim, f.read(4*dim))
                # Store vectors for words present in our Lexicon to save RAM
                if word in self.lexicon:
                    self.glove[word] = np.array(vector, dtype=np.float32)

        # 8. Initialize spaCy
        self.nlp = spacy.load('en_core_web_sm', disable=['parser', 'ner'])
        
        self.barrel_cache = {}

        end_time = time.time()
        print(f"Search Engine ready! Startup took {end_time - start_time:.2f} seconds.", flush=True)

    def get_word_id(self, word):
        return self.lexicon.get(word.lower())

    def load_barrel(self, barrel_id):
        if barrel_id in self.barrel_cache:
            return self.barrel_cache[barrel_id]
        barrel_path = os.path.join(self.index_dir, f"barrel_{barrel_id}.bin")
        if not os.path.exists(barrel_path): return {}
        with open(barrel_path, "rb") as f:
            data = pickle.load(f)
            self.barrel_cache[barrel_id] = data
            return data

    def get_suggestions(self, prefix):
        prefix = prefix.lower()
        curr = self.trie_root
        for char in prefix:
            if char not in curr['c']:
                return []
            curr = curr['c'][char]
        return curr['s']

    def semantic_search(self, query, top_n=10):
        start_time = time.time()
        doc = self.nlp(query.lower())
        query_words = [token.lemma_ for token in doc if token.is_alpha and not token.is_stop]
        
        if not query_words: query_words = query.lower().split()
        
        query_vecs = []
        for word in query_words:
            if word in self.glove:
                query_vecs.append(self.glove[word])
        
        if not query_vecs:
            return [], 0
            
        q_vec = np.mean(query_vecs, axis=0)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0: q_vec = q_vec / q_norm
        
        # Cosine similarity via dot product (since vectors are normalized)
        similarities = np.dot(self.doc_vectors, q_vec)
        
        top_indices = np.argsort(similarities)[-top_n:][::-1]
        
        results = []
        for idx in top_indices:
            isbn = self.vector_isbns[idx]
            score = float(similarities[idx])
            meta = self.metadata_cache.get(isbn, ["Unknown"]*5)
            results.append({
                "isbn": isbn, "score": score, "title": meta[0],
                "publisher": meta[1], "year": meta[2], "image_url": meta[3], "rating": meta[4]
            })
            
        return results, time.time() - start_time

    def search(self, query, top_n=10):
        start_time = time.time()
        doc = self.nlp(query.lower())
        query_words = [token.lemma_ for token in doc if token.is_alpha and not token.is_stop]
        
        if not query_words: query_words = query.lower().split()

        word_hits = {}
        for word in query_words:
            w_id = self.get_word_id(word)
            if w_id:
                barrel_id = (w_id - 1) // 10000
                barrel_data = self.load_barrel(barrel_id)
                hits = barrel_data.get(w_id, [])
                if hits: word_hits[w_id] = hits

        if not word_hits: return [], time.time() - start_time

        doc_scores = defaultdict(float)
        k1, b = 1.5, 0.75
        for w_id, isbns in word_hits.items():
            idf = self.idf_values.get(w_id, 0)
            for isbn in isbns:
                doc_len = self.doc_lengths.get(isbn, self.avg_dl)
                f_qd = 1 
                score = idf * (f_qd * (k1 + 1)) / (f_qd + k1 * (1 - b + b * (doc_len / self.avg_dl)))
                doc_scores[isbn] += score

        ranked_isbns = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        results = []
        for isbn, score in ranked_isbns:
            meta = self.metadata_cache.get(isbn, ["Unknown"]*5)
            results.append({
                "isbn": isbn, "score": score, "title": meta[0],
                "publisher": meta[1], "year": meta[2], "image_url": meta[3], "rating": meta[4]
            })
            
        return results, time.time() - start_time

def main():
    engine = SearchEngine()
    print("\n--- Digital Library Advanced Search ---")
    print("Commands: 'suggest <prefix>', 'semantic <query>', or normal query.")
    while True:
        try:
            query = input("\nQuery/Command: ").strip()
            if not query: continue
            if query.lower() == 'quit': break
            
            if query.lower().startswith("suggest "):
                prefix = query[len("suggest "):].strip()
                suggs = engine.get_suggestions(prefix)
                print(f"Suggestions for '{prefix}': {', '.join(suggs) if suggs else 'None'}")
                continue

            if query.lower().startswith("semantic "):
                q = query[len("semantic "):].strip()
                results, duration = engine.semantic_search(q)
                print(f"Semantic Results for '{q}' ({duration*1000:.2f} ms):")
            else:
                results, duration = engine.search(query)
                print(f"Keyword Results for '{query}' ({duration*1000:.2f} ms):")
            
            if not results:
                print("No matches found.")
            else:
                for i, res in enumerate(results, 1):
                    print(f"{i}. [{res['isbn']}] {res['title']}")
                    print(f"   Score: {res['score']:.4f} | Publisher: {res['publisher']} ({res['year']})")
                    print(f"   Image: {res['image_url']}")
                    print("-" * 30)
                
        except KeyboardInterrupt: break
        except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    main()
