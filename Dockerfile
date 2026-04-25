FROM python:3.12-slim AS backend-builder

# System deps for spacy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    pandas \
    spacy \
    numpy \
    requests \
    python-dotenv

# Download spaCy English model
RUN python -m spacy download en_core_web_sm

# ── Frontend build stage ──
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .

# Set the API base to empty string so it uses relative URLs via nginx
RUN sed -i "s|http://localhost:8000||g" src/App.tsx
RUN npm run build

# ── Final runtime image ──
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages from builder
COPY --from=backend-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

# Copy project source code
COPY backend/ ./backend/
COPY search_engine/ ./search_engine/
COPY indexer/ ./indexer/

# Copy data directories INTO the image (required for HF Spaces — no volume mounts)
COPY books_data/ ./books_data/
COPY embeddings/ ./embeddings/

# Ensure writable directories exist for runtime contributions
RUN mkdir -p /app/books_data/index \
             /app/books_data/new_content

# Set PYTHONPATH so the backend can locate search_engine modules
ENV PYTHONPATH=/app
ENV PROJECT_ROOT=/app

# Nginx config: serve frontend on 7860 + proxy API to backend on 8000
RUN cat > /etc/nginx/sites-available/default <<'NGINX'
server {
    listen 7860;
    server_name _;

    # Frontend (React SPA)
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /search {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    location /suggest {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    location /books {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    location /proxy-image {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    location = /api {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
    }
}
NGINX

# Entrypoint script — no env logging, chmod for non-root HF user
RUN cat > /app/start.sh <<'EOF'
#!/bin/bash
set -e

# Grant write access for HF's non-root user
chmod -R 777 /app
chmod -R 777 /var/lib/nginx
chmod -R 777 /var/log/nginx
chmod -R 777 /run

# Start nginx in background
nginx

# Start backend on port 8000 (proxied by nginx on 7860)
cd /app
exec python backend/main.py
EOF
RUN chmod +x /app/start.sh

# HF Spaces requires port 7860
EXPOSE 7860

CMD ["/app/start.sh"]
