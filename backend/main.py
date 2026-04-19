import sys
import os
import requests
import struct
import random
import time
from fastapi import FastAPI, Query, Response, HTTPException
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
async def add_book(entry: BookEntry):
    """
    Manually adds a new folio entry. 
    Saves it as a CSV snippet in the watcher's dropzone.
    """
    try:
        # 1. Generate logic
        isbn = str(random.randint(1000000000, 9999999999))
        
        # 2. Path
        new_content_dir = r"d:\MyProjects\DigitalLibrary\books_data\new_content"
        os.makedirs(new_content_dir, exist_ok=True)
        filename = f"manual_{isbn}.csv"
        filepath = os.path.join(new_content_dir, filename)
        
        # 3. Headers: ISBN;Book-Title;Book-Author;Year-Of-Publication;Publisher;Image-URL-S;Image-URL-M;Image-URL-L;Average-Rating
        # Use placeholders for S/M as we only care about L
        csv_row = f"{isbn};{entry.title};{entry.author};{entry.year};{entry.publisher};https://via.placeholder.com/150;https://via.placeholder.com/300;{entry.image_url};{entry.rating}"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("ISBN;Book-Title;Book-Author;Year-Of-Publication;Publisher;Image-URL-S;Image-URL-M;Image-URL-L;Average-Rating\n")
            f.write(csv_row)
            
        return {
            "status": "success",
            "message": f"Book '{entry.title}' committed to archive.",
            "isbn": isbn,
            "processed_locally": False, # Will be handled by watcher
            "latency_ms": 0
        }
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
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
