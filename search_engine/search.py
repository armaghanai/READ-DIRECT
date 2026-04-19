import pickle
import json
import csv
import os
import time
import spacy
import math
from collections import defaultdict

class SearchEngine:
    def __init__(self):
        self.index_dir = r"d:\MyProjects\DigitalLibrary\books_data\index"
        self.lexicon_file = r"d:\MyProjects\DigitalLibrary\books_data\lexicon.csv"
        
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
            
        # 6. Initialize spaCy
        self.nlp = spacy.load('en_core_web_sm', disable=['parser', 'ner'])
        
        # Cache for barrels to avoid repeated disk I/O during a single session if needed
        # For a one-off script, we load on demand.
        self.barrel_cache = {}

        end_time = time.time()
        print(f"Search Engine ready! Startup took {end_time - start_time:.2f} seconds.", flush=True)

    def get_word_id(self, word):
        return self.lexicon.get(word.lower())

    def load_barrel(self, barrel_id):
        if barrel_id in self.barrel_cache:
            return self.barrel_cache[barrel_id]
        
        barrel_path = os.path.join(self.index_dir, f"barrel_{barrel_id}.bin")
        if not os.path.exists(barrel_path):
            return {}
            
        with open(barrel_path, "rb") as f:
            data = pickle.load(f)
            self.barrel_cache[barrel_id] = data
            return data

    def search(self, query, top_n=10):
        start_time = time.time()
        
        # 1. Preprocess Query
        doc = self.nlp(query.lower())
        query_words = [token.lemma_ for token in doc if token.is_alpha and not token.is_stop]
        
        if not query_words:
            # Fallback if all words are stop words
            query_words = query.lower().split()

        # 2. Fetch Document Sets for each query word
        # word_docs[word_id] = [isbn1, isbn2, ...]
        word_hits = {}
        relevant_word_ids = []
        
        for word in query_words:
            w_id = self.get_word_id(word)
            if w_id:
                barrel_id = (w_id - 1) // 10000
                barrel_data = self.load_barrel(barrel_id)
                hits = barrel_data.get(w_id, [])
                if hits:
                    word_hits[w_id] = hits
                    relevant_word_ids.append(w_id)

        if not word_hits:
            return [], time.time() - start_time

        # 3. Calculate BM25 Scores
        # We only score documents that contain AT LEAST ONE of the query terms
        # For a multi-word search, documents containing more words will naturally score higher
        doc_scores = defaultdict(float)
        
        k1 = 1.5
        b = 0.75
        
        for w_id, isbns in word_hits.items():
            idf = self.idf_values.get(w_id, 0)
            
            for isbn in isbns:
                doc_len = self.doc_lengths.get(isbn, self.avg_dl)
                
                # Assume frequency in doc is 1 for metadata search
                f_qd = 1 
                
                # BM25 formula component
                score = idf * (f_qd * (k1 + 1)) / (f_qd + k1 * (1 - b + b * (doc_len / self.avg_dl)))
                doc_scores[isbn] += score

        # 4. Sort and return results
        ranked_isbns = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        
        results = []
        for isbn, score in ranked_isbns:
            meta = self.metadata_cache.get(isbn, ["Unknown", "Unknown", "Unknown", "Unknown", "Unknown"])
            results.append({
                "isbn": isbn,
                "score": score,
                "title": meta[0],
                "publisher": meta[1],
                "year": meta[2],
                "image_url": meta[3],
                "rating": meta[4]
            })
            
        duration = time.time() - start_time
        return results, duration

def main():
    engine = SearchEngine()
    
    print("\n--- Digital Library Search ---")
    while True:
        try:
            query = input("\nEnter search query (or 'quit' to exit): ").strip()
            if query.lower() == 'quit':
                break
            if not query:
                continue
                
            results, duration = engine.search(query)
            
            print(f"\nResults for '{query}' ({duration*1000:.2f} ms):")
            if not results:
                print("No matches found.")
                continue
                
            for i, res in enumerate(results, 1):
                print(f"{i}. [{res['isbn']}] {res['title']}")
                print(f"   Publisher: {res['publisher']} ({res['year']}) | Rating: {res['rating']}")
                print(f"   Image: {res['image_url']}")
                print(f"   Score: {res['score']:.4f}")
                print("-" * 40)
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error during search: {e}")

if __name__ == "__main__":
    main()
