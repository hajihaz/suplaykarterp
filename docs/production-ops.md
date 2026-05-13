# HajiHaz AI Production Ops

## Included in this hardening pass

- Automated backup archive creation from the admin API
- Backup retention cleanup
- SMTP or webhook alert support
- ntfy-compatible webhook alerts for free external notifications
- Runtime watchdog script
- User-systemd service templates for the app and watchdog
- Scheduled maintenance runner for backups, public health checks, metrics, and log cleanup
- One-command deploy and rollback shell scripts
- Staging Docker compose scaffold
- External health-check GitHub Actions workflow scaffold
- VPS security audit shell script

## Suggested VPS setup

1. Keep the FastAPI app behind your reverse proxy on `127.0.0.1:8091`.
2. Install the user services if lingering is available:

   ```bash
   mkdir -p ~/.config/systemd/user
   cp ops/vps/hajihaz-app.service ~/.config/systemd/user/
   cp ops/vps/hajihaz-watchdog.service ~/.config/systemd/user/
   cp ops/vps/hajihaz-watchdog.timer ~/.config/systemd/user/
   cp ops/vps/hajihaz-maintenance.service ~/.config/systemd/user/
   cp ops/vps/hajihaz-maintenance.timer ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now hajihaz-app.service hajihaz-watchdog.timer hajihaz-maintenance.timer
   ```

   If the VPS user does not have `loginctl enable-linger`, use the same commands via CloudPanel cron jobs instead:
   - `@reboot /home/hhaiapp/htdocs/hajihaz.82.29.160.39.sslip.io/run_ollama.sh`
   - `@reboot /home/hhaiapp/htdocs/hajihaz.82.29.160.39.sslip.io/run_hajihaz.sh`
   - `*/10 * * * * cd /home/hhaiapp/htdocs/hajihaz.82.29.160.39.sslip.io && ./.venv/bin/python backend/scripts/runtime_watchdog.py >> logs/app/watchdog.log 2>&1`
   - `15 */6 * * * cd /home/hhaiapp/htdocs/hajihaz.82.29.160.39.sslip.io && ./.venv/bin/python backend/scripts/ops_maintenance.py scheduled >> logs/app/maintenance.log 2>&1`

3. Configure one or both alert channels:
   - `ALERT_WEBHOOK_URL`
   - `ALERT_EMAIL_HOST`, `ALERT_EMAIL_USER`, `ALERT_EMAIL_PASSWORD`, `ALERT_EMAIL_FROM`, `ALERT_EMAIL_TO`

   A free no-login webhook option is `https://ntfy.sh/<your-topic>`. The alert dispatcher sends ntfy-friendly titles and tags automatically.

4. Set `PUBLIC_BASE_URL` on the server so audits and health tooling reference the correct public URL.

## Deploy and rollback

- Deploy a release archive into the live directory:

  ```bash
  ops/vps/deploy_release.sh /path/to/release.tar.gz
  ```

- Roll back from a saved release snapshot:

  ```bash
  ops/vps/rollback_release.sh /home/USER/releases/hajihaz/20260404-101500
  ```

## External health checks

If you later push this repo to GitHub, add the repository secret `HAJIHAZ_HEALTH_URL` and the included workflow will probe your public `/health` endpoint from outside the server every 15 minutes.
