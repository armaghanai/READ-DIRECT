import pandas as pd
import spacy
import csv
from collections import Counter
import os

def build_lexicon():
    print("Loading spaCy model...", flush=True)
    try:
        # Load the small English model, disabling parser and ner for speed
        nlp = spacy.load('en_core_web_sm', disable=['parser', 'ner'])
    except OSError:
        print("SpaCy model 'en_core_web_sm' not found. Downloading...", flush=True)
        from spacy.cli import download
        download('en_core_web_sm')
        nlp = spacy.load('en_core_web_sm', disable=['parser', 'ner'])
        
    print("Starting NLP processing for books...", flush=True)
    csv_file = r"d:\MyProjects\DigitalLibrary\books_data\books.csv"
    lexicon_file = r"d:\MyProjects\DigitalLibrary\books_data\lexicon.csv"
    
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found.", flush=True)
        return

    # Specific domain stop words we want to exclude
    domain_stop_words = {
        'book', 'publish', 'publisher', 'publishing', 'novel', 'press', 'inc', 'ltd', 
        'company', 'group', 'co', 'corp', 'corporation', 'llc', 'publication', 
        'volume', 'edition', 'series', 'paperback', 'hardcover', 'audio', 'media',
        'author', 'title', 'print', 'text', 'story', 'tale', 'read', 'reader'
    }
    
    # Keeping Nouns, Verbs, Adjectives, and Proper Nouns for search engine
    allowed_pos = {'NOUN', 'VERB', 'ADJ', 'PROPN'}
    word_counter = Counter()

    try:
        print(f"Loading CSV from {csv_file}...", flush=True)
        df = pd.read_csv(csv_file, sep=';', on_bad_lines='skip', encoding='latin-1', low_memory=False)
        total_rows = len(df)
        print(f"Successfully loaded {total_rows} rows.", flush=True)
    except Exception as e:
        print(f"Error loading CSV: {e}", flush=True)
        return

    print("Preparing combined text...", flush=True)
    # Fill NaN and combine columns, and LOWERCASE everything for perfect lemmatization
    # Lowercasing ensures "Books" -> "book", "Mysteries" -> "mystery"
    df['combined_text'] = (
        df['Book-Title'].fillna('') + ' ' + 
        df['Book-Author'].fillna('') + ' ' + 
        df['Publisher'].fillna('')
    ).str.lower()
    
    print("Starting spaCy NLP pipeline with batches...", flush=True)
    
    # Process the text through spaCy using nlp.pipe for efficiency
    batch_size = 1000
    for i, doc in enumerate(nlp.pipe(df['combined_text'], batch_size=batch_size, n_process=1)):
        if (i + 1) % 1000 == 0:
            print(f"Progress: [{i + 1} / {total_rows}] books parsed...", flush=True)
            
        lemmatized_words = []
        for token in doc:
            # We only want alphabetic words that are NOT default stop words and match allowed POS
            # Note: in lowercased text, many Proper Nouns will be tagged as NOUN
            if token.is_alpha and not token.is_stop and token.pos_ in allowed_pos:
                lemma = token.lemma_.lower()
                
                # Filter out our domain-specific stop words
                if lemma not in domain_stop_words and token.lower_ not in domain_stop_words:
                    lemmatized_words.append(lemma)
                    
        word_counter.update(lemmatized_words)
        
    print(f"Parsing complete. Found {len(word_counter)} unique search terms.", flush=True)
    print("Writing to lexicon.csv...", flush=True)
    
    # Store the results
    with open(lexicon_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['word_id', 'word', 'frequency'])
        
        word_id = 1
        for word, freq in word_counter.most_common():
            writer.writerow([word_id, word, freq])
            word_id += 1
            
    print("Lexicon successfully created at:", lexicon_file, flush=True)

if __name__ == "__main__":
    build_lexicon()
