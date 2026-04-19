import struct
import pickle
import os
import csv
import numpy as np

def load_glove_bin(path):
    print(f"Loading GloVe vectors from {path}...", flush=True)
    embeddings = {}
    with open(path, 'rb') as f:
        header = f.read(8)
        word_count, dim = struct.unpack('ii', header)
        for _ in range(word_count):
            word_len = struct.unpack('i', f.read(4))[0]
            word = f.read(word_len).decode('utf-8', errors='ignore')
            vector = struct.unpack('f'*dim, f.read(4*dim))
            embeddings[word] = np.array(vector, dtype=np.float32)
    print(f"Loaded {len(embeddings)} vectors.", flush=True)
    return embeddings, dim

def generate_embeddings():
    glove_path = r"d:\MyProjects\DigitalLibrary\embeddings\glove.6B.100d.bin"
    lexicon_file = r"d:\MyProjects\DigitalLibrary\books_data\lexicon.csv"
    forward_index_file = r"d:\MyProjects\DigitalLibrary\books_data\index\forward_index.bin"
    output_vecs = r"d:\MyProjects\DigitalLibrary\books_data\index\doc_vectors.npy"
    output_isbns = r"d:\MyProjects\DigitalLibrary\books_data\index\vector_isbns.bin"
    
    # 1. Load GloVe
    glove, dim = load_glove_bin(glove_path)
    
    # 2. Load Lexicon mapping ID -> Word
    print("Loading Lexicon map...", flush=True)
    id_to_word = {}
    with open(lexicon_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            id_to_word[int(row['word_id'])] = row['word']
            
    # 3. Load Forward Index
    print("Loading Forward Index...", flush=True)
    with open(forward_index_file, 'rb') as f:
        forward_index = pickle.load(f)
        
    # 4. Generate Book Embeddings
    print("Generating book embeddings...", flush=True)
    isbns = []
    vectors = []
    
    count = 0
    total = len(forward_index)
    
    for isbn, word_ids in forward_index.items():
        count += 1
        if count % 10000 == 0:
            print(f"Processed {count}/{total} books...", flush=True)
            
        doc_vecs = []
        for w_id in word_ids:
            word = id_to_word.get(w_id)
            if word and word in glove:
                doc_vecs.append(glove[word])
        
        if doc_vecs:
            # Average vector (Centroid)
            doc_vec = np.mean(doc_vecs, axis=0)
            # Normalize for cosine similarity calculation (inner product will then be cosine)
            norm = np.linalg.norm(doc_vec)
            if norm > 0:
                doc_vec = doc_vec / norm
        else:
            doc_vec = np.zeros(dim, dtype=np.float32)
            
        vectors.append(doc_vec)
        isbns.append(isbn)
        
    # 5. Save
    print("Saving document vectors...", flush=True)
    np.save(output_vecs, np.array(vectors, dtype=np.float32))
    with open(output_isbns, 'wb') as f:
        pickle.dump(isbns, f, protocol=pickle.HIGHEST_PROTOCOL)
        
    print("Embeddings generated and saved successfully!", flush=True)

if __name__ == "__main__":
    generate_embeddings()
