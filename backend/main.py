import sys
import os
import requests
import struct
import random
import time
import subprocess
from fastapi import FastAPI, Query, Header, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional

# Add project root to path so we can import search_engine
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from search_engine.search import SearchEngine

app = FastAPI(title="Digital Library API", description="Minimal Latency Hybrid Search Engine")

# Enable CORS for React frontend (Vite defaults to 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Search Engine as a singleton
engine = SearchEngine()

# Initialize API Auth
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

ADMIN_KEY = os.environ.get("ADMIN_API_KEY")
if not ADMIN_KEY:
    raise ValueError("CRITICAL: ADMIN_API_KEY env variable is required but missing. Add it to your .env file.")

class BookEntry(BaseModel):
    title: str
    author: str
    publisher: str
    year: str
    image_url: str
    rating: float = Field(..., ge=0, le=10)

@app.get("/")
async def root():
    return {"message": "Digital Library Search Engine API is online.", "developer": "Armaghan Mahmood Shams"}

@app.get("/search")
async def search(q: str = Query(..., min_length=1), top_n: int = 15):
    results, duration = engine.hybrid_search(q, top_n=top_n)
    return {
        "query": q,
        "results": results,
        "latency_ms": round(duration * 1000, 2),
        "count": len(results)
    }

@app.get("/suggest")
async def suggest(q: str = Query(..., min_length=1)):
    suggestions = engine.get_suggestions(q)
    return {
        "prefix": q,
        "suggestions": suggestions
    }

@app.post("/books")
async def add_book(entry: BookEntry, x_api_key: str = Header(None)):
    """
    Manually adds a new folio entry. 
    Saves it as a CSV snippet in the watcher's dropzone.
    """
    if x_api_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized API Key")
    try:
        # 1. Generate logic
        isbn = str(random.randint(1000000000, 9999999999))
        
        # 2. Path
        new_content_dir = r"d:\MyProjects\DigitalLibrary\books_data\new_content"
        os.makedirs(new_content_dir, exist_ok=True)
        filepath = os.path.join(new_content_dir, "new_books.csv")
        
        file_exists = os.path.exists(filepath)
        
        # 3. CSV Row preparation
        # ISBN;Book-Title;Book-Author;Year-Of-Publication;Publisher;Image-URL-S;Image-URL-M;Image-URL-L;Average-Rating
        csv_row = f"{isbn};{entry.title};{entry.author};{entry.year};{entry.publisher};https://via.placeholder.com/150;https://via.placeholder.com/300;{entry.image_url};{entry.rating}"
        
        with open(filepath, "a", encoding="utf-8") as f:
            if not file_exists or os.stat(filepath).st_size == 0:
                f.write("ISBN;Book-Title;Book-Author;Year-Of-Publication;Publisher;Image-URL-S;Image-URL-M;Image-URL-L;Average-Rating\n")
            f.write(csv_row + "\n")
            
        return {
            "status": "success",
            "message": f"Book '{entry.title}' committed to archive.",
            "isbn": isbn,
            "processed_locally": False, # Will be handled by watcher
            "latency_ms": 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/books/{isbn}/rate")
async def update_rating(isbn: str, rating: float = Query(..., ge=0, le=10), x_api_key: str = Header(None)):
    """
    Update a book's rating. Saves to a local CSV and dynamically replaces 
    """
    if x_api_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized API Key")
    try:
        new_content_dir = r"d:\MyProjects\DigitalLibrary\books_data\new_content"
        os.makedirs(new_content_dir, exist_ok=True)
        filepath = os.path.join(new_content_dir, "new_ratings.csv")
        file_exists = os.path.exists(filepath)
        
        # Calculate trailing average with active metadata cache
        final_rating = rating
        if hasattr(engine, "metadata_cache") and isbn in engine.metadata_cache:
            meta = list(engine.metadata_cache[isbn])
            old_idx = 5 if len(meta) == 6 else 4
            old_rating = float(meta[old_idx])
            if old_rating > 0:
                final_rating = round((old_rating + rating) / 2.0, 1)
        elif hasattr(engine, "delta_data") and engine.delta_data and "metadata" in engine.delta_data and isbn in engine.delta_data["metadata"]:
            meta = list(engine.delta_data["metadata"][isbn])
            old_idx = 5 if len(meta) == 6 else 4
            old_rating = float(meta[old_idx])
            if old_rating > 0:
                final_rating = round((old_rating + rating) / 2.0, 1)

        with open(filepath, "a", encoding="utf-8") as f:
            if not file_exists or os.stat(filepath).st_size == 0:
                f.write("ISBN;Rating\n")
            f.write(f"{isbn};{final_rating}\n")
            
        # Dynamically inject into search engine metadata cache
        if hasattr(engine, "metadata_cache") and isbn in engine.metadata_cache:
            meta = list(engine.metadata_cache[isbn])
            if len(meta) == 6:
                meta[5] = str(final_rating)
            elif len(meta) == 5:
                meta[4] = str(final_rating)
            engine.metadata_cache[isbn] = tuple(meta)
            engine.cache.clear() # purge front cache

        # Update in delta_data if present
        if hasattr(engine, "delta_data") and engine.delta_data and "metadata" in engine.delta_data and isbn in engine.delta_data["metadata"]:
            meta = list(engine.delta_data["metadata"][isbn])
            if len(meta) == 6:
                meta[5] = str(final_rating)
            elif len(meta) == 5:
                meta[4] = str(final_rating)
            engine.delta_data["metadata"][isbn] = tuple(meta)
            engine.cache.clear()

        return {"status": "success", "isbn": isbn, "new_rating": final_rating}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/proxy-image")
async def proxy_image(url: str):
    """
    Proxies images to avoid mixed-content (HTTP/HTTPS) blockages and CORS issues.
    Enhanced to follow redirects and handle common image server restrictions.
    """
    if not url or not url.startswith("http"):
        return Response(status_code=400)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        # Use allow_redirects=True (default) and a robust user agent
        response = requests.get(url, headers=headers, timeout=10, stream=True)
        
        # If the direct URL fails, try stripping potential Amazon tracking params
        if response.status_code != 200 and "amazon.com" in url:
            # Simple attempt to clean Amazon URLs if they fail
            clean_url = url.split("._")[0] + ".jpg" if "._" in url else url
            if clean_url != url:
                response = requests.get(clean_url, headers=headers, timeout=10, stream=True)

        if response.status_code == 200:
            return Response(content=response.content, media_type=response.headers.get("content-type", "image/jpeg"))
        else:
            return Response(status_code=response.status_code, content=f"Source returned {response.status_code}")
            
    except Exception as e:
        return Response(status_code=500, content=f"Proxy error: {str(e)}")

if __name__ == "__main__":
    watcher_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "search_engine", "watcher.py")
    watcher_proc = subprocess.Popen([sys.executable, watcher_path])
    print(f"Started background watcher service (PID {watcher_proc.pid})")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
