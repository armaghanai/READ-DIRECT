import sys
import os
import time

# Add search_engine to path
sys.path.append(r"d:\MyProjects\DigitalLibrary\search_engine")
from search import SearchEngine

def benchmark():
    print("Starting benchmark...")
    engine = SearchEngine()
    
    test_queries = [
        "Potter",
        "mystery",
        "Harry Potter and Chamber of Secrets",
        "Programming in Python for beginners"
    ]
    
    for q in test_queries:
        # Run once to warm up (load any barrels)
        _, _ = engine.search(q)
        
        # Run benchmark
        start = time.time()
        results, duration = engine.search(q)
        end = time.time()
        
        print(f"Query: '{q}'")
        print(f"  Duration: {duration*1000:.2f} ms")
        print(f"  Found: {len(results)} results")
        print("-" * 20)

if __name__ == "__main__":
    benchmark()
