# Google Play Store Submission Checklist

End-to-end checklist for submitting Suplaykart Staff to Google Play. Cross off as you go.

> The first submission takes **2–6 hours**. Re-submissions for updates take **15 minutes**.

---

## 1. Developer account setup (one time, ~$25 one-time fee)

- [ ] Google Play Console account created (https://play.google.com/console)
- [ ] $25 one-time registration fee paid
- [ ] Identity verification completed (Google sends an email)
- [ ] Tax + banking info filled in (required even for free apps)

---

## 2. App identity

| Field | Value |
|---|---|
| App name | **Suplaykart Staff** |
| Short name (on launcher) | **Suplaykart** |
| Package name (immutable) | `com.suplaykart.staff` |
| Default language | English (India) |
| Category | Business |
| Tags | `business`, `productivity`, `attendance`, `payroll` |

---

## 3. Store listing — required assets

| Asset | Spec | Source |
|---|---|---|
| **App icon** | 512×512 PNG, 32-bit, no transparency | `icons/icon-512.png` ✅ |
| **Feature graphic** | 1024×500 PNG/JPG, no transparency | TO CREATE — see template below |
| **Phone screenshots** | min 2, max 8. 16:9 or 9:16. PNG/JPG. min side 320 px, max 3840 px | Take 4–6 from a Pixel emulator |
| **7-inch tablet screenshots** | optional, recommended | Same as phone but on a 7" emulator |
| **10-inch tablet screenshots** | optional, recommended | Same as phone but on a 10" emulator |
| **Promo video** | optional, YouTube URL | Skip for v1 |

### Screenshots to capture (suggested order)

1. Login screen with role chips
2. Employee dashboard (the greeting + punch tile + tasks)
3. Manager team attendance with the live activity strip
4. Admin live attendance map (the geofenced OpenStreetMap)
5. Salary engine with the entries table
6. Profile + announcements view

### Feature graphic template (1024×500)

Quick recipe in any image editor:
- Background: gradient `#070b14` → `#0f1729` (matches `--bg`)
- Left side: the `S` monogram from `icons/icon-512.png`, scaled to 280×280
- Right side: stacked text:
  - `Suplaykart Staff` (Sora Bold, ~64 pt, white)
  - `Workforce OS · Realtime store ERP` (Inter Medium, ~26 pt, `#b8c4dc`)
- Subtle blue glow behind the icon

---

## 4. Content rating

- [ ] Complete the IARC questionnaire in Play Console → "Content rating"
- Expected result: **Everyone** (no violence, no gambling, no user-generated content visible to other users)
- Note: chat/messaging features are internal to the company only — answer "No" to "Does your app allow users to interact with other users"

---

## 5. Data safety form (required — be honest, Google audits this)

Suplaykart Staff collects:

| Data | Collected? | Shared? | Purpose | Required? |
|---|---|---|---|---|
| Email address | Yes | No | Account, sign-in | Required |
| Name | Yes | No | Account display | Required |
| Phone number | Yes | No | Account | Optional |
| Photos | Yes | No | Profile picture | Optional |
| Approximate location | Yes | No | Attendance verification (geofence) | Required for punch-in |
| Precise location | Yes | No | Attendance verification | Required for punch-in |
| App activity (in-app actions, audit logs) | Yes | No | Compliance, internal audit | Required |
| Payment info / financial info | No | — | — | — |
| Crash logs | No (not currently) | — | — | — |
| Diagnostics | No | — | — | — |

Encryption:
- [x] Data is encrypted in transit (HTTPS to Supabase)
- [x] Users can request deletion of their data (Supabase dashboard → delete user)

---

## 6. Privacy policy

Required even for free apps. Must be reachable at a stable public URL.

Minimal compliant policy template (save as `privacy.html`, host on Vercel or Notion public page):

```
PRIVACY POLICY — Suplaykart Staff
Effective: <date>
Operator: Suplaykart / Hajihaz
Contact: iamhajihaz@gmail.com

What we collect
- Account info (email, name, phone)
- Profile photo (optional, stored in Supabase Storage)
- Attendance & location data (only while the app is in use, only to verify
  you are within the store geofence)
- In-app actions (audit log entries for compliance)

How we use it
- To run the staff workforce system: attendance, tasks, salary, leaves.
- We never sell your data or share it with advertisers.

Storage
- All data is stored in Supabase (Postgres). Encrypted in transit (HTTPS).

Your rights
- Request deletion: email iamhajihaz@gmail.com and we'll erase your account.

Children
- This app is not intended for users under 18.

Changes
- We'll update this page if we change anything material.
```

- [ ] Privacy policy URL ready: `https://staff.suplaykart.com/privacy` (or wherever you host it)
- [ ] URL is publicly accessible (no auth wall)
- [ ] URL pasted into Play Console → App content → Privacy policy

---

## 7. Permissions declaration

Required because the app requests **location** (sensitive) at runtime.

Location permissions disclosure:

> "Suplaykart Staff uses your location to verify you punch in/out from within the store premises. Location is only accessed while you actively use the app. We do not share or sell your location data."

- [ ] Filled in: Play Console → App content → Permissions → Sensitive permissions → Location

Camera permission (less strict — Google considers it standard):
- [ ] Justified: "Take a profile photo for your staff card"

---

## 8. App bundle upload — Internal Testing track first

Always use Internal Testing for the first upload. Faster review (instant for internal), and you can iterate.

```bash
# Build the AAB
npm run cap:bundle
# → android/app/build/outputs/bundle/release/app-release.aab
```

Then in Play Console:

1. **Testing → Internal testing → Create new release**
2. Upload `app-release.aab`
3. **Release name**: `v1.0.0 (1)` (Capacitor uses versionCode 1 by default)
4. Release notes: copy from the box below
5. **Save → Review release → Start rollout**
6. Add testers: **Testing → Internal testing → Testers → Create email list**
7. Share the **opt-in URL** with your test team

### Release notes (v1.0.0)

```
First release of Suplaykart Staff — Workforce OS.

• Attendance with geofence-verified punch in/out
• Tasks: assign, complete, sync across the team in realtime
• Salary engine with PDF payslips
• Leave requests, announcements, audit log
• Dark/light themes, fully offline-capable PWA
• Available as a web app and an installable Android app
```

---

## 9. Promote to Closed Testing → Production

Path: Internal → Closed → Production. Each stage gets reviewed and you can pause if anything breaks.

### Closed Testing (1–7 day review)

- [ ] Set up an email list of 20+ testers (Google requires this for "ready for production" status)
- [ ] Run closed testing for a minimum of **14 days** with at least **20 testers** (Google policy as of 2024 for new apps)
- [ ] Collect feedback via Internal Test track tester groups

### Production rollout

- [ ] Promote the same AAB from Closed → Production (no rebuild needed)
- [ ] Start with **20% rollout** so a problem only affects 1 in 5 users
- [ ] Monitor crash-free rate for 48 hours
- [ ] Scale to 50% → 100% once crash-free rate stays > 99.5%

---

## 10. Post-launch — required compliance items

- [ ] Set up Google Play Crashlytics (or Sentry) — Google flags apps that hide crashes
- [ ] Set up the developer email so users can reach you (`iamhajihaz@gmail.com`)
- [ ] Respond to user reviews within 48 hours (improves store ranking)
- [ ] Update your "App content → Data safety" form within 30 days if you change what you collect

---

## 11. Version bumping for future releases

Each release needs a new `versionCode` (integer) and `versionName` (string).

Edit `android/app/build.gradle`:

```groovy
defaultConfig {
  versionCode 2          // ← bump by 1 for each release
  versionName "1.0.1"    // ← human-readable
}
```

Then:

```bash
npx cap sync android
npm run cap:bundle
# upload the new AAB in Play Console
```

---

## Quick reference — what Google asks for vs. where we have it

| Play Console asks for | We have it in |
|---|---|
| App icon 512×512 | `icons/icon-512.png` |
| Feature graphic 1024×500 | **TO CREATE** |
| Phone screenshots | **TO CAPTURE** (from emulator) |
| Privacy policy URL | **TO HOST** (template above) |
| Short description (80 chars) | "Realtime ERP for store staff — attendance, salary, tasks, leaves." |
| Full description (4000 chars) | See README.md "Highlights" section |
| App category | Business |
| Tags | business, productivity, attendance, payroll |
| Content rating | Everyone |
| Target audience | 18+ (workplace tool) |
| Data safety form | See section 5 above |
| App bundle | `android/app/build/outputs/bundle/release/app-release.aab` |
| Release notes | See section 8 above |

---

Powered by **ALLBEE SOLUTIONS**.
