---
title: READ DIRECT
emoji: 📚
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
suggested_storage: small
---

# Digital Library Platform

A high-performance, dynamic archival literature search engine constructed entirely offline. This ecosystem blends **FastAPI**, **React (Vite)**, and a custom **Hybrid NLP Search Engine** with GloVe embeddings to enable instant searching of millions of out-of-print books.

## Architecture Highlights

1. **Frontend (React + Vite)**
   - Custom Glassmorphism UI rendering dynamic `bento-box` style result cards.
   - Intelligent auto-scrolling fallback logic for missing image assets (`onError` proxy handling).
   - "Contribute Folio" manual entry pipeline securely connecting to backend drops.

2. **Backend (FastAPI)**
   - `/search`: Serves instantaneous results using pre-compiled RAM indices consisting of inverted indexes and vector dot-products.
   - `/proxy-image`: Native Python proxying layer bypassing strict HTTP/HTTPS mixed-content cors lockouts from legacy archival databases.
   - **Watcher Process Node:** A discrete `watcher.py` NLP service runs constantly in the background using `subprocess.Popen` to ingest newly contributed books (via `new_books.csv`) into the delta index every 15 seconds.

3. **Hybrid Search Engine Engine (`search_engine/`)**
   - Combines traditional keyword BM25 retrieval with dense vector (GloVe-100d / spaCy) semantic mapping.
   - Built exactly for scale: Uses binary memory mapping files (`.bin`) and heavily sharded index barrels to operate entirely offline without an external SQL database.

## System Requirements
- Python 3.10+
- Node.js v18+
- Pre-downloaded GloVe vector binaries (`glove.6B.100d.bin`)

## Execution

Ensure that your `backend/.env` file is generated with `ADMIN_API_KEY=your-admin-key`.

### 1. Boot the Backend & Watcher
The NLP engine dynamically boots its own watcher daemon natively upon port allocation.
```bash
cd backend
python main.py
```

### 2. Boot the Edge Frontend
Launch the frontend client:
```bash
cd frontend
npm install
npm run dev
```

Navigate to `http://localhost:5173` entirely bypassing cloud latency. 

## Contribution & Authentication
To add new books to the physical disc arrays or adjust the 1-10 overall trailing average ratings, interact with the floating **CONTRIBUTE FOLIO** button respectively. You will be elegantly asked for the password if you have the access.
