import pickle
import json
import csv
import os
import time
import spacy
import math
import struct
import numpy as np
from collections import defaultdict, OrderedDict

class SearchEngine:
    def __init__(self):
        project_root = os.environ.get("PROJECT_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.index_dir = os.path.join(project_root, "books_data", "index")
        self.lexicon_file = os.path.join(project_root, "books_data", "lexicon.csv")
        self.glove_path = os.path.join(project_root, "embeddings", "glove.6B.100d.bin")
        self.delta_file = os.path.join(self.index_dir, "delta_index.bin")
        
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
            
        # 4. Load Metadata Cache
        with open(os.path.join(self.index_dir, "metadata_cache.bin"), "rb") as f:
            self.metadata_cache = pickle.load(f)
            
        # 5. Load Autocomplete Trie
        self.trie_file = os.path.join(self.index_dir, "autocomplete_trie.bin")
        self.trie_mtime = 0
        self.trie_root = None
        self.load_trie()

        # 6. Load Semantic Data & Main Index
        self.doc_vectors = np.load(os.path.join(self.index_dir, "doc_vectors.npy"))
        with open(os.path.join(self.index_dir, "vector_isbns.bin"), "rb") as f:
            self.vector_isbns = pickle.load(f)
        self.isbn_to_idx = {isbn: i for i, isbn in enumerate(self.vector_isbns)}

        with open(os.path.join(self.index_dir, "doc_multipliers.bin"), "rb") as f:
            raw_multipliers = pickle.load(f)
            self.bm25_multipliers = np.array([raw_multipliers.get(isbn, 0.0) for isbn in self.vector_isbns], dtype=np.float32)

        # 7. Load Incremental Delta Index
        self.delta_data = None
        self.delta_mtime = 0
        self.load_delta()

        # 8. Filtered GloVe word vectors
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

        # 9. LRU Cache
        self.cache = OrderedDict()
        self.cache_size = 10

        # 10. spaCy
        self.nlp = spacy.load('en_core_web_sm', disable=['parser', 'ner'])
        self.barrel_cache = {}

        end_time = time.time()
        print(f"Search Engine ready! Startup took {end_time - start_time:.2f} seconds.", flush=True)

    def load_trie(self):
        if os.path.exists(self.trie_file):
            current_mtime = os.path.getmtime(self.trie_file)
            if current_mtime > self.trie_mtime:
                try:
                    with open(self.trie_file, 'rb') as f:
                        self.trie_root = pickle.load(f)
                    self.trie_mtime = current_mtime
                    print("Autocomplete Trie reloaded.")
                except:
                    pass

    def load_delta(self):
        if os.path.exists(self.delta_file):
            current_mtime = os.path.getmtime(self.delta_file)
            if current_mtime > self.delta_mtime:
                try:
                    with open(self.delta_file, 'rb') as f:
                        self.delta_data = pickle.load(f)
                    self.delta_mtime = current_mtime
                    # Reload Trie as well
                    self.load_trie()
                    # Clear cache when index changes
                    self.cache.clear()
                    print(f"Delta index updated ({len(self.delta_data['isbns'])} new books). Cache cleared.")
                except:
                    pass

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
        self.load_delta() # Check for updates
        
        # Check Cache
        if query in self.cache:
            print("[CACHE HIT]")
            self.cache.move_to_end(query)
            return self.cache[query], 0.0

        start_time = time.time()
        doc = self.nlp(query.lower())
        query_words = [token.lemma_ for token in doc if token.is_alpha and not token.is_stop]
        if not query_words: query_words = query.lower().split()

        # --- 1. Main Search (Vectorized) ---
        bm25_total = np.zeros(self.total_docs, dtype=np.float32)
        for word in query_words:
            w_id = self.get_word_id(word)
            if w_id:
                idf = self.idf_values.get(w_id, 0)
                barrel_id = (w_id - 1) // 10000
                barrel_data = self.load_barrel(barrel_id)
                hit_isbns = barrel_data.get(w_id, [])
                indices = [self.isbn_to_idx[isbn] for isbn in hit_isbns if isbn in self.isbn_to_idx]
                if indices:
                    bm25_total[indices] += float(idf) * self.bm25_multipliers[indices]

        kw_max = np.max(bm25_total)
        norm_kw = bm25_total / kw_max if kw_max > 0 else bm25_total
        
        semantic_scores = np.zeros(self.total_docs, dtype=np.float32)
        query_vecs = [self.glove[w] for w in query_words if w in self.glove]
        
        if query_vecs:
            q_vec = np.mean(query_vecs, axis=0)
            q_norm = np.linalg.norm(q_vec)
            if q_norm > 0: q_vec = q_vec / q_norm
            semantic_scores = np.dot(self.doc_vectors, q_vec)
            semantic_scores[semantic_scores < 0.35] = 0

        # Combine Main
        main_final = (0.6 * norm_kw) + (0.4 * semantic_scores)
        
        # Pick top ones from main but also check Delta
        combined_candidates = []
        for idx in np.argsort(main_final)[-top_n:][::-1]:
            score = float(main_final[idx])
            if score > 0:
                isbn = self.vector_isbns[idx]
                combined_candidates.append((isbn, score, "main"))

        # --- 2. Delta Search ---
        if self.delta_data and self.delta_data["isbns"]:
            delta_kw = defaultdict(float)
            for word in query_words:
                if word in self.delta_data["keywords"]:
                    idf = self.idf_values.get(self.get_word_id(word), 2.0) # Approx IDF for delta
                    for isbn in self.delta_data["keywords"][word]:
                        delta_kw[isbn] += idf # Simplified BM25 for delta
            
            delta_sem = np.zeros(len(self.delta_data["isbns"]), dtype=np.float32)
            if query_vecs:
                delta_vec_matrix = np.array(self.delta_data["vectors"])
                delta_sem = np.dot(delta_vec_matrix, q_vec)
                delta_sem[delta_sem < 0.35] = 0
            
            # Combine Delta
            delta_max_kw = max(delta_kw.values()) if delta_kw else 1.0
            for i, isbn in enumerate(self.delta_data["isbns"]):
                kw_s = delta_kw.get(isbn, 0.0) / delta_max_kw
                sem_s = delta_sem[i]
                final_s = (0.6 * kw_s) + (0.4 * sem_s)
                if final_s > 0:
                    combined_candidates.append((isbn, final_s, "delta"))

        # --- 3. Final Merge & Sort ---
        combined_candidates.sort(key=lambda x: x[1], reverse=True)
        results = []
        for isbn, score, source in combined_candidates[:top_n]:
            if source == "main":
                raw_meta = self.metadata_cache.get(isbn, ["Unknown"]*6)
            else:
                raw_meta = self.delta_data["metadata"].get(isbn, ["Unknown"]*6)
            
            # Robust unpacking: handle 5-field vs 6-field metadata
            # 5 fields: [Title, Publisher, Year, Image, Rating]
            # 6 fields: [Title, Author, Publisher, Year, Image, Rating]
            if len(raw_meta) == 5:
                # Pad with 'Unknown' author at index 1
                meta = [raw_meta[0], "Unknown", raw_meta[1], raw_meta[2], raw_meta[3], raw_meta[4]]
            else:
                meta = raw_meta

            final_score = float(score)
            try:
                if float(meta[5]) == 0:
                    final_score *= 0.5 # Penalty for books with 0 rating
            except: pass

            results.append({
                "isbn": isbn, "score": final_score, "title": meta[0],
                "author": meta[1], "publisher": meta[2], "year": meta[3], 
                "image_url": meta[4], "rating": meta[5]
            })

        # Re-sort after penalty
        results.sort(key=lambda x: x["score"], reverse=True)

        duration = time.time() - start_time
        # Store in Cache
        self.cache[query] = results
        if len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)
            
        return results, duration

def main():
    engine = SearchEngine()
    print("\n" + "="*50)
    print("--- Digital Library Hybrid Search (Incremental & Cached) ---")
    print("Developed by Armaghan Mahmood Shams")
    print("="*50)
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
            print(f"\nResults for '{query}' ({duration*1000:.2f} ms):")
            
            if not results:
                print("No matches found.")
            else:
                for i, res in enumerate(results, 1):
                    print(f"{i}. [{res['isbn']}] {res['title']}")
                    print(f"   Score: {res['score']:.4f} | Publisher: {res['publisher']} ({res['year']}) | Rating: {res['rating']}/10")
                    print(f"   Image: {res['image_url']}")
                    print("-" * 30)
                
        except KeyboardInterrupt: break
        except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    main()
