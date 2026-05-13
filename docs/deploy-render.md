# Deploy HajiHaz AI on Render

This project includes a ready-to-use [render.yaml](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/render.yaml>) Blueprint.

## What this Blueprint does

- Creates a Docker-based backend web service
- Attaches a persistent disk at `/app/backend/data` so SQLite survives deploys
- Creates a Docker-based frontend web service
- Injects the backend private `host:port` into the frontend automatically via `API_BASE_HOSTPORT`

## Before you start

1. Push this project to GitHub, GitLab, or Bitbucket.
2. Keep [`.dockerignore`](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/.dockerignore>) in place so Render does not upload local caches, your virtualenv, or local secrets.
3. Decide whether SQLite is enough for your first production launch.

Use SQLite if:
- this is a personal single-user deployment
- you want the simplest first launch

Move to Postgres later if:
- you want multi-user scale
- you want stronger durability and database tooling

## Step by step

1. Open Render and choose `New` -> `Blueprint`.
2. Connect the repo that contains this project.
3. Render will detect [render.yaml](</Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/render.yaml>).
4. Review the two services:
- `hajihaz-backend`
- `hajihaz-frontend`
5. Provide these environment variables when prompted:
- `ADMIN_PASSWORD`
- `ANTHROPIC_API_KEY`
- `CORS_ORIGINS`
6. For `CORS_ORIGINS`, use your frontend URL after Render assigns it, for example `https://hajihaz-frontend.onrender.com`.
7. Deploy the Blueprint.
8. Wait for the backend health check on `/health` to pass.
9. Open the frontend service URL and test:
- login
- chat
- add a document in admin
- ask a question that should retrieve the new document

## Recommended Render settings

- Keep the backend disk attached unless you migrate off SQLite.
- Use a paid plan for the backend if you want the service to stay warm and keep the disk.
- Add a custom domain to the frontend service once the default URL is working.

## Production checks

Run these after the deploy:

1. Visit the frontend URL and confirm the homepage loads.
2. Login at `/admin`.
3. Add a short test document like `Render deployment smoke test`.
4. Ask the chat to recall that exact phrase.
5. Confirm `/admin` shows `Claude API: Configured` after adding a valid Anthropic key.

## Notes

- The frontend does not need a public browser-side backend URL anymore. It proxies through Next route handlers under `/api/*`.
- Because the frontend talks to the backend server-side, `CORS_ORIGINS` matters mainly for any direct browser calls to the backend, not for the normal app flow.
