import pandas as pd
import pickle
import json
import csv
import os
import math

def precalculate():
    lexicon_file = r"d:\MyProjects\DigitalLibrary\books_data\lexicon.csv"
    forward_index_file = r"d:\MyProjects\DigitalLibrary\books_data\index\forward_index.bin"
    books_file = r"d:\MyProjects\DigitalLibrary\books_data\books.csv"
    index_dir = r"d:\MyProjects\DigitalLibrary\books_data\index"
    
    # N is total documents
    N = 271360 

    print("Loading lexicon and calculating IDF values...", flush=True)
    # IDF = log(1 + (N - n(q) + 0.5) / (n(q) + 0.5))
    idf_values = {}
    with open(lexicon_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            w_id = int(row['word_id'])
            freq = int(row['frequency'])
            # Using standard BM25 IDF formula
            idf = math.log10(1 + (N - freq + 0.5) / (freq + 0.5))
            idf_values[w_id] = idf
            
    print(f"Calculated IDFs for {len(idf_values)} words.", flush=True)
    with open(os.path.join(index_dir, "idf_values.bin"), "wb") as f:
        pickle.dump(idf_values, f, protocol=pickle.HIGHEST_PROTOCOL)

    print("Loading forward index to calculate document lengths...", flush=True)
    with open(forward_index_file, 'rb') as f:
        forward_index = pickle.load(f)
    
    doc_lengths = {}
    total_tokens = 0
    for isbn, word_ids in forward_index.items():
        length = len(word_ids)
        doc_lengths[isbn] = length
        total_tokens += length
        
    avg_dl = total_tokens / N
    print(f"Average Document Length: {avg_dl}", flush=True)

    # Pre-calculate BM25 Doc Multipliers (for f(q,d)=1 case)
    # Multiplier = (k1 + 1) / (1 + k1 * (1 - b + b * (L(d) / avg_dl)))
    k1, b = 1.5, 0.75
    doc_multipliers = {}
    for isbn, length in doc_lengths.items():
        m = (k1 + 1) / (1 + k1 * (1 - b + b * (length / avg_dl)))
        doc_multipliers[isbn] = float(m)
    
    print("Saving stats and multipliers...", flush=True)
    stats = {
        "avg_dl": avg_dl,
        "total_docs": N
    }
    with open(os.path.join(index_dir, "search_stats.json"), "w") as f:
        json.dump(stats, f)
        
    with open(os.path.join(index_dir, "doc_lengths.bin"), "wb") as f:
        pickle.dump(doc_lengths, f, protocol=pickle.HIGHEST_PROTOCOL)

    with open(os.path.join(index_dir, "doc_multipliers.bin"), "wb") as f:
        pickle.dump(doc_multipliers, f, protocol=pickle.HIGHEST_PROTOCOL)

    print("Building Metadata Cache from books.csv...", flush=True)
    metadata_cache = {}
    # Columns we need: ISBN(0), Title(1), Year(3), Publisher(4), ImageL(7), Rating(8)
    try:
        df = pd.read_csv(books_file, sep=';', on_bad_lines='skip', encoding='latin-1', low_memory=False)
        for _, row in df.iterrows():
            isbn = str(row['ISBN'])
            metadata_cache[isbn] = [
                str(row['Book-Title']),
                str(row['Book-Author']),
                str(row['Publisher']),
                str(row['Year-Of-Publication']),
                str(row['Image-URL-L']),
                str(row['Average-Rating'])
            ]
        print(f"Cached metadata for {len(metadata_cache)} books.", flush=True)
    except Exception as e:
        print(f"Error building metadata cache: {e}")
        return

    with open(os.path.join(index_dir, "metadata_cache.bin"), "wb") as f:
        pickle.dump(metadata_cache, f, protocol=pickle.HIGHEST_PROTOCOL)

    print("Pre-calculation successfully completed!", flush=True)

if __name__ == "__main__":
    precalculate()
