import pandas as pd
import spacy
import pickle
import json
import csv
import os
from collections import defaultdict

def build_indices():
    lexicon_file = r"d:\MyProjects\DigitalLibrary\books_data\lexicon.csv"
    books_file = r"d:\MyProjects\DigitalLibrary\books_data\books.csv"
    index_dir = r"d:\MyProjects\DigitalLibrary\books_data\index"
    
    if not os.path.exists(index_dir):
        os.makedirs(index_dir)

    print("Loading lexicon into memory...", flush=True)
    # Map word -> word_id
    lexicon = {}
    with open(lexicon_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            lexicon[row['word']] = int(row['word_id'])
            
    print(f"Loaded {len(lexicon)} words from lexicon.", flush=True)

    print("Loading spaCy model...", flush=True)
    try:
        # Try loading directly
        nlp = spacy.load('en_core_web_sm', disable=['parser', 'ner'])
    except OSError:
        print("SpaCy model 'en_core_web_sm' not found. Downloading...", flush=True)
        # Use spacy.cli from global scope or import specifically
        from spacy.cli import download
        download('en_core_web_sm')
        nlp = spacy.load('en_core_web_sm', disable=['parser', 'ner'])
    
    # Same settings as build_lexicon.py for consistency
    allowed_pos = {'NOUN', 'VERB', 'ADJ', 'PROPN'}
    domain_stop_words = {
        'book', 'publish', 'publisher', 'publishing', 'novel', 'press', 'inc', 'ltd', 
        'company', 'group', 'co', 'corp', 'corporation', 'llc', 'publication', 
        'volume', 'edition', 'series', 'paperback', 'hardcover', 'audio', 'media',
        'author', 'title', 'print', 'text', 'story', 'tale', 'read', 'reader'
    }

    print("Loading books CSV data...", flush=True)
    try:
        df = pd.read_csv(books_file, sep=';', on_bad_lines='skip', encoding='latin-1', low_memory=False)
        total_rows = len(df)
        print(f"Loaded {total_rows} books.", flush=True)
    except Exception as e:
        print(f"Error loading books.csv: {e}")
        return
    
    print("Lowercasing combined text fields...", flush=True)
    df['combined_text'] = (
        df['Book-Title'].fillna('') + ' ' + 
        df['Book-Author'].fillna('') + ' ' + 
        df['Publisher'].fillna('')
    ).str.lower()

    forward_index = {}
    inverted_index = defaultdict(list)

    print("Starting indexing pipeline (Forward & Inverted)...", flush=True)
    batch_size = 2000
    isbns = df['ISBN'].tolist()
    
    # Use nlp.pipe for high-performance batch processing
    for i, doc in enumerate(nlp.pipe(df['combined_text'], batch_size=batch_size, n_process=1)):
        if (i + 1) % 5000 == 0:
            print(f"Progress: [{i + 1} / {total_rows}] books processed...", flush=True)
        
        isbn = str(isbns[i])
        word_ids = set() # Unique word IDs per document
        
        for token in doc:
            if token.is_alpha and not token.is_stop and token.pos_ in allowed_pos:
                lemma = token.lemma_ # Already lowercased because input was lower
                if lemma in lexicon and lemma not in domain_stop_words:
                    w_id = lexicon[lemma]
                    word_ids.add(w_id)
        
        # Sort for consistency and convert to list
        word_list = sorted(list(word_ids))
        
        # Forward Index: ISBN -> List of Word IDs
        forward_index[isbn] = word_list
        
        # Inverted Index Accumulation: Word ID -> List of ISBNs
        for w_id in word_list:
            inverted_index[w_id].append(isbn)

    print("Saving Forward Index (Binary)...", flush=True)
    with open(os.path.join(index_dir, "forward_index.bin"), "wb") as f:
        pickle.dump(forward_index, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    print("Generating Forward Index Sample...", flush=True)
    forward_sample = {isbn: forward_index[isbn] for isbn in list(forward_index.keys())[:10]}
    with open(os.path.join(index_dir, "forward_sample.json"), "w") as f:
        json.dump(forward_sample, f, indent=4)

    print("Distributing into Inverted Barrels (Binary)...", flush=True)
    # Divide based on Numeric Word ID ranges (10,000 words per barrel)
    barrels = defaultdict(dict)
    for w_id, doc_list in inverted_index.items():
        # word_id starts at 1
        b_id = (w_id - 1) // 10000
        barrels[b_id][w_id] = doc_list
        
    for b_id, data in barrels.items():
        barrel_path = os.path.join(index_dir, f"barrel_{b_id}.bin")
        with open(barrel_path, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"Barrel {b_id} saved ({len(data)} words).", flush=True)

    print("Generating Inverted Index Sample...", flush=True)
    inverted_sample = {str(w_id): inverted_index[w_id] for w_id in sorted(list(inverted_index.keys()))[:10]}
    with open(os.path.join(index_dir, "inverted_sample.json"), "w") as f:
        json.dump(inverted_sample, f, indent=4)

    print("Indexing successfully completed!", flush=True)

if __name__ == "__main__":
    build_indices()
