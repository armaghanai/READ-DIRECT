import csv
import pickle
import os

def build_trie():
    lexicon_file = r"d:\MyProjects\DigitalLibrary\books_data\lexicon.csv"
    output_file = r"d:\MyProjects\DigitalLibrary\books_data\index\autocomplete_trie.bin"
    
    print("Building Autocomplete Trie...", flush=True)
    # root format: {'c': {}, 's': []} where 'c' is children dict, 's' is suggestions
    root = {'c': {}, 's': []}
    
    # Load lexicon and sort by frequency descending to easily pick top 5
    words_data = []
    with open(lexicon_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row['word']
            freq = int(row['frequency'])
            words_data.append((word, freq))
            
    # Sort by frequency so that when we insert, we can easily maintain top 5
    words_data.sort(key=lambda x: x[1], reverse=True)
    
    for word, freq in words_data:
        curr = root
        for char in word:
            if char not in curr['c']:
                curr['c'][char] = {'c': {}, 's': []}
            curr = curr['c'][char]
            
            # Maintain top 5 suggestions at each node
            if len(curr['s']) < 5:
                curr['s'].append(word)
                
    print(f"Trie built with {len(words_data)} words. Saving...", flush=True)
    with open(output_file, 'wb') as f:
        pickle.dump(root, f, protocol=pickle.HIGHEST_PROTOCOL)
    print("Trie saved successfully!", flush=True)

if __name__ == "__main__":
    build_trie()
