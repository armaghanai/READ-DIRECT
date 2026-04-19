import struct
import os

def peek_glove(path):
    with open(path, 'rb') as f:
        # Try to read word count and dim
        header = f.read(8)
        if len(header) < 8: return
        
        # Possible formats: [int word_count, int dim] or [int dim, int word_count]
        # or just binary data starting immediately.
        # Let's try to interpret as two 4-byte integers.
        v1, v2 = struct.unpack('ii', header)
        print(f"Header: {v1}, {v2}")
        
        # Based on my previous Get-Content:
        # 128 26 6 0 (v1) -> 400,000 in little endian? (0x00061a80 = 400000)
        # 100 0 0 0 (v2) -> 100
        # YES! Little-endian 4-byte ints.
        
        print(f"Word Count: {v1}")
        print(f"Dimensionality: {v2}")
        
        # Read a few words
        for _ in range(3):
            word_len_bytes = f.read(4)
            if not word_len_bytes: break
            word_len = struct.unpack('i', word_len_bytes)[0]
            word = f.read(word_len).decode('utf-8', errors='ignore')
            vector = struct.unpack('f'*v2, f.read(4*v2))
            print(f"Word: {word}, First 3 values: {vector[:3]}")

if __name__ == "__main__":
    peek_glove(r"d:\MyProjects\DigitalLibrary\embeddings\glove.6B.100d.bin")
