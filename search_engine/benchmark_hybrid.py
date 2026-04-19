import sys
import os
import time

# Add search_engine to path
sys.path.append(r"d:\MyProjects\DigitalLibrary\search_engine")
from search import SearchEngine

def benchmark():
    print("Starting Hybrid Benchmark...")
    engine = SearchEngine()
    
    test_queries = [
        "Harry Potter",
        "mystery murder",
        "witchcraft and sorcery",
        "fast racing cars"
    ]
    
    for q in test_queries:
        # Initial run to pre-load components
        _, _ = engine.hybrid_search(q)
        
        start = time.time()
        results, duration = engine.hybrid_search(q)
        end = time.time()
        
        print(f"\nQuery: '{q}'")
        print(f"  Duration: {duration*1000:.2f} ms")
        if results:
            # Check scores
            max_score = results[0]['score']
            print(f"  Top Result: {results[0]['title']}")
            print(f"  Top Score: {max_score:.4f} (KW: {results[0]['kw_score']:.2f}, SEM: {results[0]['sem_score']:.2f})")
            
            # Verify timing requirement
            if duration * 1000 > 200:
                print("  WARNING: Exceeded 200ms limit!")
            else:
                print("  Performance: OK (<200ms)")
        else:
            print("  No results found.")
        print("-" * 30)

if __name__ == "__main__":
    benchmark()
