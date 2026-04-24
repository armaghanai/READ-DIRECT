import os
import time
import pandas as pd
import spacy
import pickle
import numpy as np
import csv
import struct
from collections import defaultdict

def load_glove_bin(path):
    embeddings = {}
    with open(path, 'rb') as f:
        header = f.read(8)
        word_count, dim = struct.unpack('ii', header)
        for _ in range(word_count):
            word_len = struct.unpack('i', f.read(4))[0]
            word = f.read(word_len).decode('utf-8', errors='ignore')
            vector = struct.unpack('f'*dim, f.read(4*dim))
            embeddings[word] = np.array(vector, dtype=np.float32)
    return embeddings, dim

class IncrementalIndexer:
    def __init__(self):
        project_root = os.environ.get("PROJECT_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.new_content_dir = os.path.join(project_root, "books_data", "new_content")
        self.index_dir = os.path.join(project_root, "books_data", "index")
        self.main_csv = os.path.join(project_root, "books_data", "books.csv")
        self.lexicon_file = os.path.join(project_root, "books_data", "lexicon.csv")
        self.delta_file = os.path.join(self.index_dir, "delta_index.bin")
        self.glove_path = os.path.join(project_root, "embeddings", "glove.6B.100d.bin")
        
        self.processed_files = set()
        self.total_new_books = 0
        self.delta_data = {"keywords": defaultdict(list), "vectors": [], "isbns": [], "metadata": {}}
        
        # Load existing delta if exists
        if os.path.exists(self.delta_file):
            try:
                with open(self.delta_file, 'rb') as f:
                    self.delta_data = pickle.load(f)
                self.total_new_books = len(self.delta_data["isbns"])
                print(f"Loaded existing delta index with {self.total_new_books} books.")
            except:
                pass

        # Load Trie for dynamic updates
        self.trie_file = os.path.join(self.index_dir, "autocomplete_trie.bin")
        self.trie_root = None
        if os.path.exists(self.trie_file):
            with open(self.trie_file, 'rb') as f:
                self.trie_root = pickle.load(f)

        print("Initializing NLP and GloVe for watcher...")
        self.nlp = spacy.load('en_core_web_sm', disable=['parser', 'ner'])
        self.glove, self.dim = load_glove_bin(self.glove_path)
        
        self.allowed_pos = {'NOUN', 'VERB', 'ADJ', 'PROPN'}
        self.domain_stop_words = {
            'book', 'publish', 'publisher', 'publishing', 'novel', 'press', 'inc', 'ltd', 
            'company', 'group', 'co', 'corp', 'corporation', 'llc', 'publication', 
            'volume', 'edition', 'series', 'paperback', 'hardcover', 'audio', 'media',
            'author', 'title', 'print', 'text', 'story', 'tale', 'read', 'reader'
        }

    def process_file(self, file_path):
        print(f"Processing new file: {file_path}")
        try:
            df = pd.read_csv(file_path, sep=';', on_bad_lines='skip', encoding='latin-1', low_memory=False)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return

        if 'Book-Title' not in df.columns:
            return

        for _, row in df.iterrows():
            try:
                isbn = str(row['ISBN'])
                if isbn in self.delta_data["metadata"]: continue # Already in delta
                
                # 1. Metadata
                # Extract Image-URL-L (Large). User reported 'nan' because they were pointing to another field.
                image_url = str(row.get('Image-URL-L', 'nan'))
                if image_url == 'nan' or not image_url.startswith('http'):
                    # Fallback if specific column is missing or empty
                    potential_urls = [str(row.get('Image-URL-M', '')), str(row.get('Image-URL-S', ''))]
                    for p in potential_urls:
                        if p.startswith('http'):
                            image_url = p
                            break

                details = [
                    str(row['Book-Title']),
                    str(row['Book-Author']),
                    str(row['Publisher']),
                    str(row['Year-Of-Publication']),
                    image_url,
                    str(row['Average-Rating'])
                ]
                self.delta_data["metadata"][isbn] = details
                self.delta_data["isbns"].append(isbn)
                
                # 2. Keywords (NLP)
                text = (str(row['Book-Title']) + ' ' + str(row['Book-Author']) + ' ' + str(row['Publisher'])).lower()
                doc = self.nlp(text)
                lemmas = []
                for token in doc:
                    if token.is_alpha and not token.is_stop and token.pos_ in self.allowed_pos:
                        lemma = token.lemma_.lower()
                        if lemma not in self.domain_stop_words:
                            lemmas.append(lemma)
                            self.delta_data["keywords"][lemma].append(isbn)
                            # Add to Trie for autocomplete
                            self.update_trie(lemma)
                
                # 3. Semantic Vector
                vecs = [self.glove[w] for w in lemmas if w in self.glove]
                if vecs:
                    avg_vec = np.mean(vecs, axis=0)
                    norm = np.linalg.norm(avg_vec)
                    if norm > 0: avg_vec = avg_vec / norm
                    self.delta_data["vectors"].append(avg_vec)
                else:
                    self.delta_data["vectors"].append(np.zeros(self.dim, dtype=np.float32))
                
                self.total_new_books += 1
            except Exception as e:
                print(f"Error processing row {row.get('ISBN', 'Unknown')}: {e}")
                continue

        # Atomic Save Delta
        temp_file = self.delta_file + ".tmp"
        with open(temp_file, 'wb') as f:
            pickle.dump(self.delta_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(temp_file, self.delta_file)
        
        # Atomic Save Trie if updated
        if self.trie_root:
            temp_trie = self.trie_file + ".tmp"
            with open(temp_trie, 'wb') as f:
                pickle.dump(self.trie_root, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(temp_trie, self.trie_file)

        print(f"Delta index and Trie updated. Total new books: {self.total_new_books}")

        if self.total_new_books >= 2000:
            self.merge_all(df) # Logic for merge

    def update_trie(self, word):
        if not self.trie_root: return
        curr = self.trie_root
        for char in word:
            if char not in curr['c']:
                curr['c'][char] = {'c': {}, 's': []}
            curr = curr['c'][char]
            if word not in curr['s']:
                curr['s'].append(word)
                # Keep only top 5 (simulating priority for new words too)
                if len(curr['s']) > 5:
                    curr['s'].pop(0) 

    def merge_all(self, last_df):
        print("THRESHOLD REACHED (2000 books). Merging Delta into Main...")
        # 1. Append to books.csv (not implemented here for safety but logic would be df.to_csv(main, mode='a'))
        # 2. Trigger re-indexing (In a real system, you'd run indexer.py)
        # 3. Clear Delta
        # For now, we'll just simulate by printing
        print("Merging process triggered. (Manual refresh of Barrels/Vectors Recommended)")
        # self.delta_data = {"keywords": defaultdict(list), "vectors": [], "isbns": [], "metadata": {}}
        # self.total_new_books = 0

    def run(self):
        print(f"Watcher started. Monitoring {self.new_content_dir} ...")
        while True:
            # 1. Process all CSV files in directory (legacy support + single file support)
            files = [f for f in os.listdir(self.new_content_dir) if f.endswith('.csv') and "ratings" not in f.lower()]
            for f in files:
                full_path = os.path.join(self.new_content_dir, f)
                # For the consolidated file, we always check it. 
                # For other files, we skip if already processed to save time.
                if f == "new_books.csv" or full_path not in self.processed_files:
                    try:
                        self.process_file(full_path)
                    except Exception as e:
                        print(f"Critical error in process_file for {f}: {e}")
                    self.processed_files.add(full_path)
            
            time.sleep(15)

if __name__ == "__main__":
    indexer = IncrementalIndexer()
    indexer.run()
