# HajiHaz AI Production Architecture

## Canonical Production Path

Use one production path for new deployments:

1. `caddy` terminates HTTPS and serves the public domain.
2. `frontend` runs the Next.js production server inside Docker.
3. `backend` runs FastAPI inside Docker on the private Docker network.
4. The browser talks to the same public origin; the frontend proxies API calls to `backend`.
5. Production environment variables live in `.env` and are injected by Docker Compose.

Canonical command:

```bash
docker compose -f docker-compose.vps.yml up -d --build
```

## Legacy / Emergency Path

The direct Hostinger path that runs Uvicorn on `127.0.0.1:8091` is an emergency recovery path only.
It is useful when Docker is unavailable or when applying a narrow hotfix, but it must not become the
main deployment pipeline because it has caused live/preview drift before.

If the emergency path is used, always run dependency installation after changing `backend/requirements.txt`:

```bash
python3 -m pip install --break-system-packages -r backend/requirements.txt
```

Then restart with:

```bash
APP_ROOT=/home/hajirp/hajihaz-app bash /home/hajirp/hajihaz-app/ops/vps/manage_hajihaz.sh restart
```

## Required Production Environment

```bash
APP_ENV=production
PUBLIC_BASE_URL=https://hajihazai.allbeesolutions.com
CORS_ORIGINS=https://hajihazai.allbeesolutions.com
SECRET_KEY=<strong random value>
ADMIN_EMAIL=<admin email>
ADMIN_PASSWORD=<initial bootstrap password>
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
RATE_LIMIT_ENABLED=true
```

Optional:

```bash
ADMIN_PASSWORD_HASH=<argon2id hash>
ANTHROPIC_API_KEY=<key>
ONLINE_SEARCH_ENABLED=true
```

## Database Evolution

Current production uses SQLite and is suitable only for low-concurrency MVP usage.
The next production-grade step is PostgreSQL:

1. Add a PostgreSQL service to Docker Compose.
2. Introduce a SQLAlchemy or SQLModel data layer.
3. Keep the existing SQLite schema as the migration source.
4. Export documents, chunks, sessions, users, and operational tables from SQLite.
5. Import into PostgreSQL with a one-time migration script.
6. Run the backend against PostgreSQL in staging before production cutover.

Do not run multi-worker SaaS traffic on the SQLite backend.

## Auth Migration Plan

The backend now accepts both legacy bearer tokens and HttpOnly session cookies.
The frontend still keeps bearer-token behavior for compatibility, but requests also use same-origin credentials.

Next safe steps:

1. Stop writing admin and user tokens to `localStorage`.
2. On app load, call `/auth/me` or `/user-auth/me` using the HttpOnly cookie.
3. Keep bearer authorization support server-side for one release.
4. Remove localStorage token fallback after live sessions have rolled over.

This avoids breaking current chat/admin behavior while moving toward XSS-resistant session storage.

## Production Drift Rules

- The live app must expose `/`, `/admin`, `/privacy-policy`, `/health`, `/robots.txt`, `/sitemap.xml`, and `/favicon.ico`.
- `/docs`, `/redoc`, and `/openapi.json` must be disabled when `APP_ENV=production`.
- Static preview files may remain as a fallback, but the canonical public app is the Docker frontend.
- Every production deployment must run health checks and one chat smoke test before being accepted.
