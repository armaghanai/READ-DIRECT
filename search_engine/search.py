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
        
        print("Initializing Optimized Search Engine... (Loading data into RAM)", flush=True)
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
            
        # 4. Load Optimized Metadata Cache
        with open(os.path.join(self.index_dir, "metadata_cache.bin"), "rb") as f:
            self.metadata_cache = pickle.load(f)
            
        # 5. Load Autocomplete Trie
        with open(os.path.join(self.index_dir, "autocomplete_trie.bin"), "rb") as f:
            self.trie_root = pickle.load(f)

        # 6. Load Semantic Data & Unified Indexing
        self.doc_vectors = np.load(os.path.join(self.index_dir, "doc_vectors.npy"))
        with open(os.path.join(self.index_dir, "vector_isbns.bin"), "rb") as f:
            self.vector_isbns = pickle.load(f)
        
        # Map ISBN to NumPy index for fast vectorized access
        self.isbn_to_idx = {isbn: i for i, isbn in enumerate(self.vector_isbns)}

        # 7. Load BM25 Doc Multipliers into NumPy array
        with open(os.path.join(self.index_dir, "doc_multipliers.bin"), "rb") as f:
            raw_multipliers = pickle.load(f)
            # Reorder multipliers to match vector_isbns order
            self.bm25_multipliers = np.array([raw_multipliers.get(isbn, 0.0) for isbn in self.vector_isbns], dtype=np.float32)

        # 8. Load GloVe word vectors (Filtered by Lexicon)
        self.glove = {}
        with open(self.glove_path, 'rb') as f:
            header = f.read(8)
            word_count, dim = struct.unpack('ii', header)
            for _ in range(word_count):
                w_len = struct.unpack('i', f.read(4))[0]
                word = f.read(w_len).decode('utf-8', errors='ignore')
                vector = struct.unpack('f'*dim, f.read(4*dim))
                if word in self.lexicon:
                    self.glove[word] = np.array(vector, dtype=np.float32)

        # 9. Initialize spaCy
        self.nlp = spacy.load('en_core_web_sm', disable=['parser', 'ner'])
        self.barrel_cache = {}

        end_time = time.time()
        print(f"Search Engine ready! Startup took {end_time - start_time:.2f} seconds.", flush=True)

    def get_word_id(self, word):
        return self.lexicon.get(word.lower())

    def load_barrel(self, barrel_id):
        if barrel_id in self.barrel_cache: return self.barrel_cache[barrel_id]
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
            if char not in curr['c']: return []
            curr = curr['c'][char]
        return curr['s']

    def hybrid_search(self, query, top_n=10):
        start_time = time.time()
        doc = self.nlp(query.lower())
        query_words = [token.lemma_ for token in doc if token.is_alpha and not token.is_stop]
        if not query_words: query_words = query.lower().split()

        # --- 1. Vectorized Keyword Path (BM25) ---
        # We calculate BM25 scores for ALL docs using NumPy
        bm25_total_scores = np.zeros(self.total_docs, dtype=np.float32)
        
        for word in query_words:
            w_id = self.get_word_id(word)
            if w_id:
                idf = self.idf_values.get(w_id, 0)
                barrel_id = (w_id - 1) // 10000
                barrel_data = self.load_barrel(barrel_id)
                hit_isbns = barrel_data.get(w_id, [])
                
                # Convert ISBN hits to NumPy indices
                indices = [self.isbn_to_idx[isbn] for isbn in hit_isbns if isbn in self.isbn_to_idx]
                if indices:
                    # Score = IDF * Multiplier
                    bm25_total_scores[indices] += float(idf) * self.bm25_multipliers[indices]

        # Normalize Keyword scores to [0,1]
        kw_max = np.max(bm25_total_scores)
        if kw_max > 0:
            norm_kw_scores = bm25_total_scores / kw_max
        else:
            norm_kw_scores = bm25_total_scores

        # --- 2. Vectorized Semantic Path ---
        semantic_scores = np.zeros(self.total_docs, dtype=np.float32)
        query_vecs = [self.glove[w] for w in query_words if w in self.glove]
        
        if query_vecs:
            q_vec = np.mean(query_vecs, axis=0)
            q_norm = np.linalg.norm(q_vec)
            if q_norm > 0: q_vec = q_vec / q_norm
            
            # Efficient matrix dot product
            semantic_scores = np.dot(self.doc_vectors, q_vec)
            # Thresholding (lower irrelevant matches)
            semantic_scores[semantic_scores < 0.35] = 0

        # --- 3. Hybrid Combination (60% KW / 40% SEM) ---
        final_scores = (0.6 * norm_kw_scores) + (0.4 * semantic_scores)

        # --- 4. Result Retrieval ---
        # Get top indices
        top_indices = np.argsort(final_scores)[-top_n:][::-1]
        
        results = []
        for idx in top_indices:
            score = float(final_scores[idx])
            if score <= 0: continue # Skip if no match at all
            
            isbn = self.vector_isbns[idx]
            meta = self.metadata_cache.get(isbn, ["Unknown"]*5)
            results.append({
                "isbn": isbn, "score": score, "title": meta[0],
                "publisher": meta[1], "year": meta[2], "image_url": meta[3], "rating": meta[4],
                "kw_score": float(norm_kw_scores[idx]),
                "sem_score": float(semantic_scores[idx])
            })
            
        duration = time.time() - start_time
        return results, duration

def main():
    engine = SearchEngine()
    print("\n--- Digital Library Hybrid Search (Optimized) ---")
    print("Commands: 'suggest <prefix>', or just enter your query.")
    while True:
        try:
            query = input("\nQuery: ").strip()
            if not query: continue
            if query.lower() == 'quit': break
            
            if query.lower().startswith("suggest "):
                prefix = query[len("suggest "):].strip()
                suggs = engine.get_suggestions(prefix)
                print(f"Suggestions for '{prefix}': {', '.join(suggs) if suggs else 'None'}")
                continue

            results, duration = engine.hybrid_search(query)
            print(f"\nHybrid Results for '{query}' ({duration*1000:.2f} ms):")
            
            if not results:
                print("No matches found.")
            else:
                for i, res in enumerate(results, 1):
                    print(f"{i}. [{res['isbn']}] {res['title']}")
                    print(f"   Score: {res['score']:.4f} (KW: {res['kw_score']:.2f}, SEM: {res['sem_score']:.2f})")
                    print(f"   Publisher: {res['publisher']} ({res['year']}) | Rating: {res['rating']}")
                    print(f"   Image: {res['image_url']}")
                    print("-" * 30)
                
        except KeyboardInterrupt: break
        except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    main()
