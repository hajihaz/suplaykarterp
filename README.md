# Suplaykart Staff — Workforce OS

A production-ready, single-file ERP for store teams. Realtime cloud-synced via Supabase, installable as a PWA on Android / iPhone / Desktop, and wrap-shippable to the Play Store via Capacitor.

> **One file is the entire app.** Open `index.html` and you're live. Everything else in this repo is deployment plumbing.

---

## Highlights

- **3 roles, one app** — Employee, Manager, Admin (role-routed at sign-in).
- **Realtime cloud sync** — every mutation fans out to all signed-in tabs via Supabase Realtime.
- **Offline-capable PWA** — installable on Android / iOS / Desktop, app shell cached by service worker.
- **Native Android wrapper** — Capacitor config included, ready for Play Store submission.
- **Geofence map** — real OpenStreetMap tiles (no API key) with a 150 m perimeter ring.
- **PDF payslips & CSV exports** — generated client-side, downloaded directly.
- **Audit logged** — every sensitive action is mirrored to `audit_logs`.
- **Single-file architecture preserved** — no build step, no framework, no bundler.

---

## Repo layout

```
.
├── index.html              ← The whole app. Open this.
├── manifest.json           ← PWA manifest
├── service-worker.js       ← PWA offline shell
├── icons/                  ← PWA + Apple-touch + maskable icons
│   ├── icon-{16,32,192,256,384,512}.png
│   ├── icon-maskable-{192,512}.png
│   ├── apple-touch-icon.png
│   └── splash/             ← iOS launch images
├── schema.sql              ← Postgres schema + RLS + storage buckets
├── vercel.json             ← Vercel routing + cache headers
├── capacitor.config.json   ← Android/iOS wrapper config
├── package.json            ← npm scripts (cap:android, vercel:deploy, etc.)
├── .gitignore
├── .npmrc
├── LICENSE
├── README.md               ← You are here
├── DEPLOYMENT.md           ← Step-by-step deploy guide
└── PRODUCTION_CHECKLIST.md ← Pre-launch QA checklist
```

---

## Quick start (5 minutes)

```bash
# 1. Clone
git clone https://github.com/<you>/suplaykart-staff.git
cd suplaykart-staff

# 2. (Optional) install tooling
npm install

# 3. Serve locally with the right MIME types & no caching
npm run start
# → opens http://localhost:5173
```

Or simpler still: just double-click `index.html`. Everything works except the service worker (browsers require `http(s)://` for SW). For a real local PWA test use `npm run start`.

---

## Supabase setup (already done if you ran `schema.sql`)

The app talks directly to your Supabase project `edbvlpippapjookhwbzw`. The anon/publishable key is embedded in `index.html` — safe to commit, RLS protects the data.

If you need to bootstrap from scratch:

1. Open Supabase → SQL editor → paste `schema.sql` → Run.
2. Provision an administrator securely through Supabase Auth using a unique password and a private, owner-controlled setup procedure.
3. Open `index.html` (locally or deployed). Sign in.

### Credentials block

At the very top of `index.html`:

```html
<script>
  window.SUPABASE_CONFIG = {
    url:     'https://edbvlpippapjookhwbzw.supabase.co',
    anonKey: 'sb_publishable_VHZbdzU92WoKglSZ2CrUNQ_eZ_5buhl',
  };
</script>
```

To rotate keys, just edit those two lines and re-deploy. **Never put your `service_role` key here.**

---

## Administrator provisioning and incident response

1. Create or recover the administrator account in the authenticated Supabase dashboard (Authentication → Users).
2. Use a strong, unique password stored in a password manager. **Never commit passwords, recovery codes, or admin setup credentials.**
3. Assign administrator privileges through a verified, owner-only setup process. Check role-based access and row-level security before production use.
4. If credentials have ever appeared in a public repository, rotate them immediately, review active sessions and logs, and assume previous Git history and forks retain copies.
5. Store any private setup details outside this public repository. Public publishable keys are not authentication secrets; service-role and secret keys must never be exposed.

---

## Deployment paths

You have three first-class deployment surfaces — all from the same `index.html`:

| Surface       | Use when                            | How                              |
|---------------|-------------------------------------|----------------------------------|
| **PWA**       | Install on phones via the browser   | Visit URL → "Install" prompt     |
| **Vercel**    | Public web hosting                  | `vercel --prod`                  |
| **Android**   | Play Store distribution             | `npm run cap:android` → Studio   |

See **[DEPLOYMENT.md](./DEPLOYMENT.md)** for full step-by-step instructions for each.

---

## What stays in sync (realtime)

Every signed-in tab subscribes to these tables and re-renders on change:

- `profiles` · `employees` · `attendance` · `attendance_sessions`
- `tasks` · `announcements` · `salary_records` · `leaves`
- `warnings` · `notifications` · `audit_logs`

Channels are deduped via a single registry (`SuplaykartCloud.subscribe`) so re-mounts never stack.

---

## PWA features

- Installable from Chrome / Edge / Safari (Add to Home Screen)
- Offline shell (cached `index.html` + icons + manifest)
- Cached map tiles (7-day TTL)
- Cached CDN libraries (Leaflet, jsPDF, supabase-js)
- Background updates with toast prompt to reload
- Custom branded install bar (Android + desktop)
- iOS safe-area insets respected (notch + home bar)
- Theme color follows light/dark mode

---

## Diagnostics

Open devtools and run:

```js
diagnostics()             // sanity-check cloud + tables + storage + SW
SuplaykartCloud.whoami()  // current authed user
SuplaykartCloud.ready()   // is the cloud client up?
hydrateFromCloud()        // force-pull fresh data
```

`diagnostics()` prints a table with: cloud-ready, session, every table's row count, storage bucket access, service-worker controller, standalone-mode flag.

---

## Tech notes

- No build step. Pure HTML + vanilla JS + Supabase JS.
- `@supabase/supabase-js@2`, password grant, persistSession: true, auto-refresh tokens.
- Realtime: Postgres changes via the default `supabase_realtime` publication, throttled to 8 events/sec.
- Service worker: cache-first shell, stale-while-revalidate for CDN assets, never-cache for Supabase calls.
- Single-file architecture preserved: integration lives in the `SuplaykartCloud` IIFE.

---

## License

MIT — see [LICENSE](./LICENSE).

Powered by **ALLBEE SOLUTIONS** · Suplaykart Staff Workforce OS
