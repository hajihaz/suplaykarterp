# Launch Runbook

Day-of go-live sequence for Suplaykart Staff. Follow top to bottom — each step verifies the previous one.

> Estimated time: **45 minutes** for first-time launch. **5 minutes** for subsequent deploys.

---

## T-minus checklist (before you start)

- [ ] Supabase project owner credentials available
- [ ] GitHub account with repo-creation permission
- [ ] Vercel account (free tier is fine to start)
- [ ] Android keystore generated and password recorded (only needed for Play Store path)
- [ ] Privacy policy URL ready (required for Play Store + iOS, plain HTML page is fine)

---

## Phase A — Supabase (10 min)

```bash
# 1. Confirm schema is in place
# Supabase dashboard → SQL editor → run schema.sql (idempotent, safe to re-run)
```

**Then create the admin user via the dashboard:**

1. Authentication → Users → **Add user**
   - Email: **owner-controlled admin address (not documented publicly)**
   - Password: **unique randomly generated credential; never commit or share it**
   - Auto-confirm: **ON only after verifying account ownership**
2. Copy the new user's UUID.
3. SQL editor → run (replace `<UUID>`):

```sql
update public.profiles
   set role='admin', full_name='Hajihaz', username='hajihaz',
       phone=NULL, address='Suplaykart HQ, Nagore, TN'
 where id='<UUID>';

insert into public.employees (id, user_id, name, role, dept, status, score, color)
values ('SKT-100', '<UUID>', 'Hajihaz', 'Founder', 'Management', 'Active', 100, '#4f8cff')
    on conflict (id) do update set user_id = excluded.user_id;
```

**Verify:**
- Authentication → Users → confirm the row exists, email confirmed
- Table editor → `profiles` → role is `admin`
- Table editor → `employees` → `SKT-100` has the user_id set

---

## Phase B — GitHub push (5 min)

```bash
cd /path/to/this/folder
git init
git add .
git commit -m "feat: suplaykart-staff production launch"
git branch -M main
git remote add origin git@github.com:<you>/suplaykart-staff.git
git push -u origin main
```

**Verify:** browse the repo on GitHub — `index.html`, `manifest.json`, `service-worker.js`, `schema.sql` all visible.

---

## Phase C — Vercel deploy (5 min)

```bash
npm install                # installs Vercel CLI + http-server
npx vercel login           # browser auth
npx vercel link            # answer "create new project"
npx vercel --prod          # deploys
```

**Wait for the URL.** Vercel returns something like `https://suplaykart-staff-<hash>.vercel.app`.

**Verify in browser:**
1. Open the URL.
2. Login screen renders. Page loads in <2s.
3. Open DevTools → Application → Service Workers → `service-worker.js` is **activated**.
4. Application → Manifest → no errors, "Installable" badge visible.

---

## Phase D — Supabase URL allow-list (2 min)

This is the one **non-obvious** step that traps everyone.

Supabase Dashboard → **Authentication → URL Configuration**:
- **Site URL**: paste your Vercel URL (e.g. `https://suplaykart-staff.vercel.app`)
- **Redirect URLs**: add the same URL **and** `https://*.vercel.app` (so preview deploys also work)
- Save

Without this, you'll get a successful sign-in then `auth callback origin mismatch` on every reload.

---

## Phase E — Smoke test (5 min)

In the deployed Vercel URL:

1. **Sign in** with the separately provisioned, owner-controlled admin credentials → lands on Admin overview.
2. **Refresh the page** → still signed in (session persistence working).
3. **Open DevTools console** → run `diagnostics()`. All checks should be green.
4. **Open a second browser** (incognito or different device) → sign in as a manager/employee account.
5. **Cross-tab realtime:** admin sends an announcement → employee sees it without refresh.
6. **Avatar upload:** Profile → upload a photo → see it appear in the admin's directory.
7. **PWA install:** Chrome's URL bar → install icon → install → opens in standalone mode.

If any of these fail, see **Rollback** below before proceeding.

---

## Phase F — Custom domain (optional, 5 min)

Vercel → Project → **Settings → Domains** → add `staff.suplaykart.com`.

- Add CNAME at your DNS provider (Vercel shows you exactly what)
- HTTPS auto-provisions within ~60 s
- **Re-do Phase D** with your custom domain as the Site URL

---

## Phase G — Android build (only if shipping APK/AAB) (15 min)

```bash
npm install
npx cap add android
npx cap sync android
npx cap open android
```

In Android Studio:

1. Wait for Gradle sync to finish.
2. **Build → Generate Signed App Bundle / APK → Android App Bundle**
3. Use your release keystore (see `DEPLOYMENT.md` for `keytool` command).
4. Output: `android/app/build/outputs/bundle/release/app-release.aab`

**Verify on a physical device:**
- Install via `adb install app-release.apk` (build a debug APK for testing first)
- Launch → opens to login screen with splash → no white flash
- Sign in → realtime works the same as web
- Punch attendance → location permission prompt appears
- Avatar upload → camera/gallery permission prompt appears

---

## Phase H — Play Store upload

See `PLAY_STORE.md` for the full submission checklist.

---

## Rollback / recovery

| Symptom | Action |
|---|---|
| **Vercel deploy broken** | `npx vercel rollback` — instantly reverts to previous production deploy |
| **App fully unreachable** | Vercel dashboard → Deployments → click prior good one → **Promote to Production** |
| **Bad code pushed to main** | `git revert HEAD && git push` — the workflow auto-deploys the revert |
| **Bad service worker stuck on users' phones** | Push a new deploy with `CACHE_VERSION` bumped in `service-worker.js`; the SW's `activate` step deletes all old caches. Worst case: tell users to "uninstall + reinstall" the PWA. |
| **Supabase DB corrupted** | Supabase Dashboard → Database → Backups → **Restore** to a prior point-in-time (free tier: 1 day; pro tier: 7 days) |
| **Auth tokens leaked / publishable key needs rotation** | Supabase → API → **Reset anon key** → update `SUPABASE_CONFIG` in `index.html` → `vercel --prod` → users will need to sign in once more |
| **Admin user locked out** | Use the dashboard to reset the password directly: Authentication → Users → click the user → "Send password reset" or "Set password" |

---

## Go/no-go gate

Don't proceed to a public/customer-facing launch until **all** of these are true:

- [ ] Vercel deploy is live and HTTPS works
- [ ] Supabase Site URL set to production URL
- [ ] Admin can sign in and stays signed in across refresh
- [ ] Realtime sync verified across two browsers
- [ ] PWA installs cleanly on at least one Android device
- [ ] CSV + PDF exports both produce real files
- [ ] Geofence map renders
- [ ] No console errors in production browser
- [ ] At least one employee + one manager test account seeded in Supabase

If shipping to Play Store also requires:

- [ ] AAB signed with release keystore
- [ ] Tested on a real (not emulator) Android device
- [ ] Privacy policy URL live and reachable
- [ ] All 8 Play Console screenshots taken
- [ ] Data safety form answers prepared (see `PLAY_STORE.md`)

---

Once every box is ticked, you're cleared to ship. Powered by **ALLBEE SOLUTIONS**.
