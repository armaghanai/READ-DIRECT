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

# Data directories (mount these as volumes for persistence)
RUN mkdir -p /app/books_data/index \
             /app/books_data/new_content \
             /app/embeddings

# Nginx config: serve frontend + proxy /api to backend
RUN cat > /etc/nginx/sites-available/default <<'NGINX'
server {
    listen 80;
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

# Entrypoint script
RUN cat > /app/start.sh <<'EOF'
#!/bin/bash
set -e

export PROJECT_ROOT=/app

# Start nginx in background
nginx

# Start backend (which also spawns watcher)
cd /app
exec python backend/main.py
EOF
RUN chmod +x /app/start.sh

# Expose port 80 (nginx) for the unified app
EXPOSE 80

ENV PROJECT_ROOT=/app
ENV ADMIN_API_KEY=admin123

CMD ["/app/start.sh"]
