# Deploy HajiHaz AI on Hostinger or any Docker VPS

This repo now includes a production VPS stack:

- [docker-compose.vps.yml](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/docker-compose.vps.yml>)
- [ops/vps/Caddyfile](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/ops/vps/Caddyfile>)

The stack runs:

- `backend` on the internal Docker network
- `frontend` on the internal Docker network
- `caddy` on ports `80` and `443` for HTTPS and reverse proxy

Because the frontend proxies `/api/*` server-side, the public domain only needs to point at the frontend through Caddy.

## Option A: Hostinger Docker Manager

1. Push this project to a Git repository.
2. In Hostinger VPS, open `Docker Manager`.
3. Create a new Compose deployment from your repository or paste the contents of [docker-compose.vps.yml](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/docker-compose.vps.yml>).
4. Upload or create an `.env` based on [`.env.example`](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/.env.example>).
5. Set these values before deploying:
- `APP_ENV=production`
- `ADMIN_PASSWORD`
- `ANTHROPIC_API_KEY`
- `PUBLIC_HOSTNAME`
- `LETSENCRYPT_EMAIL`
6. Point your domain's DNS `A` record to the VPS IP.
7. Deploy the stack.
8. Wait for Caddy to provision TLS automatically.
9. Open `https://your-domain` and test chat and admin.

## Option B: Standard Ubuntu VPS shell

1. Install Docker Engine and the Docker Compose plugin on the VPS.
2. Clone your repo onto the server.
3. Create `.env` from [`.env.example`](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/.env.example>).
4. Set:
- `APP_ENV=production`
- `ADMIN_PASSWORD`
- `ANTHROPIC_API_KEY`
- `PUBLIC_HOSTNAME`
- `LETSENCRYPT_EMAIL`
5. Open ports `80` and `443` in the VPS firewall.
6. Point your domain's DNS `A` record to the VPS IP.
7. Start the stack:

```bash
docker compose -f docker-compose.vps.yml up -d --build
```

8. Follow logs if needed:

```bash
docker compose -f docker-compose.vps.yml logs -f
```

9. Update the stack later with:

```bash
git pull
docker compose -f docker-compose.vps.yml up -d --build
```

## Production checks

1. Visit `https://your-domain`.
2. Confirm the chat UI loads.
3. Login at `https://your-domain/admin`.
4. Add a test document.
5. Ask chat about that exact document.
6. Confirm the admin panel shows `Claude API: Configured` after adding a valid Anthropic key.

## Notes

- Backend data persists in the named Docker volume `backend_data`.
- TLS certificates persist in `caddy_data`.
- If you already run another reverse proxy on the VPS, do not expose Caddy on `80` and `443` directly. Instead, connect this app behind your existing proxy and only expose the frontend container internally.
