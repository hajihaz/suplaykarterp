# Production Checklist

A pre-launch sanity sweep. Run through this before flipping the DNS to production or pushing to the Play Store.

> Tip: from devtools, run `diagnostics()` — it auto-checks most of the cloud-side items below.

---

## 1. Supabase

- [ ] `schema.sql` executed (or diffed against current schema)
- [ ] All 11 tables exist: `profiles`, `employees`, `attendance`, `attendance_sessions`, `tasks`, `announcements`, `salary_records`, `leaves`, `warnings`, `notifications`, `audit_logs`
- [ ] RLS is **enabled** on every table (Supabase → Auth → Policies; should show "RLS On" badge)
- [ ] `handle_new_user` trigger exists (Database → Triggers)
- [ ] `supabase_realtime` publication includes all 11 tables
- [ ] Storage buckets exist: `avatars` (public), `exports` (private), `payslips` (private)
- [ ] Storage policies present (`avatars_owner_write`, `avatars_public_read`, `exports_owner_rw`)

## 2. Auth

- [ ] Owner-controlled admin user provisioned in `auth.users` with a unique password stored outside the repository
- [ ] `profiles.role = 'admin'` for that user
- [ ] `employees.user_id` set on `SKT-100` to the admin's auth UUID
- [ ] Login accepts the configured administrator identifier and rejects invalid credentials
- [ ] After sign-in, role chip shows **Admin**
- [ ] Refresh the page → session auto-resumes (no re-login)
- [ ] Sign out → returns to login screen, no leaked state

## 3. Realtime

- [ ] Open the app in **two browsers** signed in as different roles
- [ ] Manager creates a task → employee sees it appear without refresh
- [ ] Admin marks salary paid → employee gets a "Salary credited" notification
- [ ] Admin sends an announcement → both managers and employees see it instantly
- [ ] Manager approves leave → employee notification updates
- [ ] Employee changes profile photo → admin's directory shows the new photo

## 4. Mutations + audit

For each, complete the action and verify it shows up in **Admin → Audit Logs**:

- [ ] Sign in / Sign out
- [ ] Punch in / Punch out
- [ ] Task complete / reopen / assign
- [ ] Salary mark paid / undo
- [ ] Leave approve / reject
- [ ] Warning issue
- [ ] Announcement send (manager + admin)
- [ ] Profile update (employee, manager, admin)
- [ ] New employee created

## 5. Exports

- [ ] Employee → Attendance → Export CSV → file downloads with correct rows
- [ ] Manager → Team Attendance → Export CSV → respects search + dept filter
- [ ] Salary → Download payslip → PDF opens with correct values
- [ ] Historical payslip download works

## 6. Geofence map

- [ ] Admin → Live Attendance → map renders with OpenStreetMap tiles
- [ ] 150 m geofence circle visible
- [ ] Store marker centered, employee pins drift over time
- [ ] Re-navigate away and back → map re-initializes cleanly (no double-render)

## 7. Storage uploads

- [ ] Profile → upload photo → file appears in Supabase → Storage → `avatars/<uid>/...`
- [ ] Same photo visible across both employee + admin views in realtime
- [ ] Remove photo → falls back to initials avatar

## 8. PWA

- [ ] DevTools → Application → Manifest → "Installable" with no errors
- [ ] DevTools → Application → Service Workers → `service-worker.js` activated
- [ ] Lighthouse → PWA category → green (or no critical failures)
- [ ] Install prompt appears (Android Chrome / desktop Chrome / Edge)
- [ ] After install, launches in standalone mode (no browser chrome)
- [ ] iOS Safari → Add to Home Screen → opens in standalone
- [ ] Theme color matches: dark `#070b14`, light `#f6f8fc`
- [ ] Safe-area insets respected on iPhone notch
- [ ] Offline test: install, kill network, reload → app shell still loads, banner shows "You are offline"

## 9. Mobile responsive

- [ ] Layout tested at: 360×640 (small Android), 390×844 (iPhone 14), 768×1024 (iPad), 1280×800 (laptop)
- [ ] Bottom-tab nav appears on mobile, sidebar on desktop
- [ ] Profile sheet (mobile) opens + closes cleanly
- [ ] Modal padding respects safe area on notched devices

## 10. Themes

- [ ] Dark mode (default) — colors correct
- [ ] Light mode — toggle from settings — full re-paint
- [ ] System theme detection on first load
- [ ] Theme persists across reload via `state.settings.theme`

## 11. Performance

- [ ] First load < 2s on 4G (Lighthouse)
- [ ] No console errors after sign-in
- [ ] No duplicate network requests
- [ ] Realtime subscriptions: exactly **11** channels open (one per table); see Network → WS → frames
- [ ] No memory leaks after navigating between pages 20 times

## 12. Security

- [ ] Anon key in `index.html` is the **publishable** / anon key — NOT `service_role`
- [ ] Vercel headers include `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`
- [ ] HTTPS enforced (no mixed content warnings)
- [ ] CSP if needed (the app currently doesn't set one — add via vercel.json if your security policy demands it)
- [ ] Supabase Auth → URL Configuration includes only your real prod domain in Site URL

## 13. Capacitor / Android (if shipping APK/AAB)

- [ ] `npx cap sync android` runs cleanly
- [ ] Build succeeds in Android Studio (no Gradle errors)
- [ ] Permissions: location prompt appears on first punch
- [ ] Camera prompt appears when user picks an avatar
- [ ] Status bar tinted dark to match the navy app background
- [ ] Splash screen shows then fades out (1500 ms)
- [ ] App icon shows correctly in launcher (use Android Studio → Image Asset → Launcher Icon, or copy from `icons/`)
- [ ] AAB signed with release keystore (not debug)
- [ ] Test on a real device, not just emulator

## 14. iOS (if shipping)

- [ ] `Info.plist` has location, camera, photos usage strings
- [ ] App icon set generated (Xcode → Assets.xcassets → AppIcon)
- [ ] Splash screen LaunchScreen.storyboard customized
- [ ] Tested on iPhone (notch handling) + iPad

## 15. Operational

- [ ] Audit logs reviewed for noisy / unintended actions
- [ ] Backup plan: Supabase database backup schedule confirmed
- [ ] Rotate keys planned (if credentials ever leak): re-issue anon key + re-deploy
- [ ] Owner of the Supabase project is documented internally
- [ ] Privacy policy URL ready (required for Play Store + iOS)
- [ ] Data retention policy decided (audit logs older than X months → archive/delete)

---

Once every box is ticked, you're ready to ship.

Powered by **ALLBEE SOLUTIONS**.
