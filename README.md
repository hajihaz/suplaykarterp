# HajiHaz AI

HajiHaz AI is a personal RAG assistant with a FastAPI backend, a Next.js frontend, SQLite-backed knowledge storage, and support for free local Ollama inference or Anthropic when you want a hosted model.

For local use on this Mac, the stable product UI is currently served directly from the FastAPI app on `http://127.0.0.1:8000`. The Next.js app on `http://127.0.0.1:3000` is optional and should be treated as a separate frontend path, not the primary local UI.

## What is included

- FastAPI backend with `health`, `auth`, `chat`, and `admin` endpoints
- SQLite schema bootstrapping with seeded starter knowledge
- Lightweight local RAG pipeline using chunking and TF-IDF style scoring
- Ollama local-model integration for zero-cost AI
- Anthropic integration with graceful fallback when you choose a hosted model
- Next.js chat UI with admin knowledge-base management
- Stable backend-served local UI on `127.0.0.1:8000`
- Bulk document import for `.txt`, `.md`, `.json`, and `.csv` files in the stable admin workspace
- Rich ingestion for `.pdf`, `.docx`, image OCR, public Google Docs, Google Sheets, Google Drive files, Notion pages, and general website imports
- Hardened session handling with hashed session storage, logout, and configurable session TTL
- Source controls for disable, reindex, and sync
- Backup creation, analytics, resource monitoring, and secret/deploy audit in the admin workspace
- Ops scripts for watchdogs, deploy, rollback, staging, and security review
- Docker and local run instructions

## Project structure

```text
backend/
  app/
frontend/
.env.example
docker-compose.yml
```

## Local setup

1. Copy `.env.example` to `.env` and fill in the secrets.
2. Backend:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
   ```

3. Frontend:

   ```bash
   cd frontend
   PATH="$PWD/../.tools/node-v20.20.2-darwin-arm64/bin:$PATH" npm install
   npm run dev
   ```

4. Open the stable local UI at `http://127.0.0.1:8000`.
5. If you want to run the separate Next.js frontend, start it and open `http://127.0.0.1:3000`.

## Free local AI mode

The project now supports a zero-cost local setup through Ollama.

1. Install Ollama on macOS from [https://ollama.com/download](https://ollama.com/download).
2. Start Ollama.
3. Pull a compact local model:

   ```bash
   ollama pull qwen2.5:1.5b-instruct
   ```

4. Keep these env values:

   ```bash
   AI_PROVIDER=ollama
   OLLAMA_BASE_URL=http://127.0.0.1:11434/api
   OLLAMA_MODEL=qwen2.5:1.5b-instruct
   ```

5. Start the backend and frontend normally.

## Simple start commands

```bash
./scripts/start_backend.sh
./scripts/start_frontend.sh
```

Recommended local usage:

- Stable product UI: `http://127.0.0.1:8000`
- Stable admin UI: `http://127.0.0.1:8000/admin`
- Optional separate Next.js frontend: `http://127.0.0.1:3000`

## Production build

```bash
cd frontend
PATH="$PWD/../.tools/node-v20.20.2-darwin-arm64/bin:$PATH" npm run build
HOSTNAME=0.0.0.0 PORT=3000 PATH="$PWD/../.tools/node-v20.20.2-darwin-arm64/bin:$PATH" npm run start
```

## Auth

- Admin email defaults to `admin@hajihaz.local`
- Admin password comes from `.env`
- You can optionally set `ADMIN_PASSWORD_HASH` to a SHA-256 hash and leave `ADMIN_PASSWORD` as a fallback or local-only secret
- `SESSION_TTL_HOURS` controls how long admin sessions stay valid before re-authentication
- `AI_PROVIDER=ollama` keeps the app on the free local path by default

## Bulk import

The stable admin UI at `http://127.0.0.1:8000/admin` supports bulk import from:

- `.txt`
- `.md` or `.markdown`
- `.json`
- `.csv`
- `.pdf`
- `.docx`
- image OCR for `.png`, `.jpg`, `.jpeg`, `.webp`, `.tif`, `.tiff`

It also supports public URL imports for:

- websites and articles
- Google Docs
- Google Sheets
- public Google Drive files
- public Notion pages

JSON files can contain a single document object, an array of document objects, or an object with a `documents` array. CSV files should include headers such as `title`, `content`, `tags`, and optionally `source`.

OCR uses `tesseract`, and scanned PDF OCR uses `pdftoppm` plus `tesseract`. If those commands are not installed on the runtime machine, image and scanned-PDF OCR will gracefully fall back to regular text extraction only.

## Deployment outline

- Backend: Render, Railway, Fly.io, or Docker on VPS
- Frontend: Vercel or Docker/Nginx with `API_BASE_URL` set at runtime so the browser can stay on same-origin `/api/*`
- Database: SQLite for single-user deployments, PostgreSQL when you want multi-user scale

## Render deployment

1. Push this project to GitHub.
2. In Render, create a new Blueprint and point it at the repo.
3. Use [render.yaml](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/render.yaml>).
4. Set these required environment variables in Render:
   - `ADMIN_PASSWORD`
   - `CORS_ORIGINS`
5. The included Blueprint now attaches a persistent disk to the backend and injects the backend private host/port into the frontend automatically.
6. After the first deploy, set a custom domain if you want public production access.

## Docker deployment

```bash
docker compose up --build
```

This starts:
- backend on `http://localhost:8000`
- frontend on `http://localhost:3000`

The frontend now proxies browser requests through Next route handlers under `/api/*`, so the backend URL is runtime-configured with `API_BASE_URL` instead of being baked into the client bundle.

## Production deployment guides

- Render: [docs/deploy-render.md](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/docs/deploy-render.md>)
- Hostinger or any VPS with Docker: [docs/deploy-hostinger-vps.md](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/docs/deploy-hostinger-vps.md>)
- Production architecture: [docs/production-architecture.md](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/docs/production-architecture.md>)
- Ops hardening: [docs/production-ops.md](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/docs/production-ops.md>)
- Full handover: [docs/hajihaz-handover.md](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/docs/hajihaz-handover.md>)

## Android path

The fastest APK path is to wrap the responsive web app in Capacitor. If you later want richer native integrations, migrate the UI to React Native while keeping the FastAPI backend unchanged.
