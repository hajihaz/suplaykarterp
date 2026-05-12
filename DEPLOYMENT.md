# Deployment Guide

This file is the canonical step-by-step for shipping Suplaykart Staff to:

1. [GitHub repository](#1-github)
2. [Vercel (web hosting)](#2-vercel)
3. [PWA install (end users)](#3-pwa-install)
4. [Capacitor / Android (Play Store)](#4-capacitor--android)
5. [iOS (TestFlight / App Store)](#5-ios-via-capacitor)
6. [Custom domain & HTTPS](#6-custom-domain--https)

> **Pre-flight:** make sure you've executed `schema.sql` against your Supabase project and seeded the admin user. See `README.md` → "Admin seed".

---

## 1. GitHub

Initial push from this folder:

```bash
git init
git add .
git commit -m "feat: production-ready Suplaykart Staff Workforce OS"
git branch -M main
git remote add origin git@github.com:<you>/suplaykart-staff.git
git push -u origin main
```

What ships and what doesn't is governed by `.gitignore` — `node_modules/`, `android/`, `ios/`, `*.keystore`, `.env*`, and `.vercel/` are all excluded.

The Supabase URL + publishable key in `index.html` **are safe to commit**. They're the public anon key designed for client-side use; RLS is what protects the data.

### Optional: GitHub Actions (lint + Vercel preview)

Drop this in `.github/workflows/deploy.yml` if you want auto-deploy on every push:

```yaml
name: Deploy
on:
  push: { branches: [main] }
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token:    ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id:   ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: --prod
```

---

## 2. Vercel

### One-time setup

1. `npm install` (installs the Vercel CLI + http-server).
2. `npx vercel login` (browser auth).
3. `npx vercel link` — answer the prompts; pick "create new project" the first time.

### Deploy

```bash
npm run vercel:deploy        # → npx vercel --prod
```

That's it. Vercel reads `vercel.json`:

- All non-asset routes rewrite to `/index.html` (SPA-style)
- `index.html`, `manifest.json`, `service-worker.js` use `must-revalidate`
- Icons + fonts get a 1-year `immutable` cache header
- Security headers: `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy: geolocation=(self), camera=(self)`
- `schema.sql` is `noindex` + `no-store`

### Preview deploys

```bash
npx vercel               # preview URL with full functionality
```

### Supabase auth allow-list

After your first Vercel deploy, copy the URL (e.g. `https://suplaykart-staff.vercel.app`) and add it in:

**Supabase → Authentication → URL Configuration**:
- **Site URL** → your prod URL
- **Redirect URLs** → your prod URL **and** the preview wildcard (`https://*.vercel.app`)

---

## 3. PWA install

Once the app is on HTTPS (any deploy: Vercel, Netlify, Cloudflare Pages, S3+CloudFront, etc.):

| Device                      | Install                                             |
|-----------------------------|-----------------------------------------------------|
| **Android (Chrome/Edge)**   | Visit URL → tap the "Install" toast (or ⋮ → Install app) |
| **iOS (Safari)**            | Share → "Add to Home Screen"                        |
| **Desktop (Chrome/Edge)**   | URL bar → install icon (right side), or ⋮ → Install |
| **Brave / Firefox mobile**  | ⋮ → Add to home screen                              |

The custom install bar in `index.html` shows automatically on Android + desktop after the user has signed in (so it's not noisy on the login screen) and re-prompts after 14 days if dismissed.

### Verifying install works

1. Open the deployed URL.
2. Open DevTools → Application → Manifest. Should show "Installable" with no errors.
3. Application → Service Workers. Should show `service-worker.js` activated.
4. Run `diagnostics()` in the console.

---

## 4. Capacitor / Android

### One-time setup

```bash
# Install dependencies
npm install

# Initialize Capacitor (uses capacitor.config.json which is already in place)
npx cap init   # ← if it asks, accept the existing config

# Add the Android platform
npx cap add android
```

This generates an `android/` folder (already gitignored). Then:

```bash
# Push the latest web assets into Android
npx cap sync android

# Open in Android Studio
npx cap open android
```

### Build a release AAB for Play Store

```bash
npm run cap:bundle
# → produces android/app/build/outputs/bundle/release/app-release.aab
```

### Required: signing key

```bash
keytool -genkey -v -keystore android.keystore \
  -alias suplaykart -keyalg RSA -keysize 2048 -validity 10000
```

Add to `android/key.properties` (gitignored):

```properties
storePassword=...
keyPassword=...
keyAlias=suplaykart
storeFile=../android.keystore
```

And in `android/app/build.gradle` inside `android { ... }`:

```groovy
signingConfigs {
  release {
    keyAlias keystoreProperties['keyAlias']
    keyPassword keystoreProperties['keyPassword']
    storeFile file(keystoreProperties['storeFile'])
    storePassword keystoreProperties['storePassword']
  }
}
buildTypes {
  release { signingConfig signingConfigs.release ; minifyEnabled true }
}
```

### Permissions you'll need to declare

In `android/app/src/main/AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />
```

Capacitor's plugins (`@capacitor/geolocation`, `@capacitor/camera`) handle the runtime permission prompts via the OS dialog. Configure friendly rationale strings under `strings.xml` if needed.

### Play Store metadata

| Field          | Value                                          |
|----------------|------------------------------------------------|
| App name       | Suplaykart Staff                               |
| Short name     | Suplaykart                                     |
| Package name   | `com.suplaykart.staff`                         |
| Category       | Business                                       |
| Content rating | Everyone                                       |
| Icon (512×512) | `icons/icon-512.png`                           |
| Feature graphic| Make a 1024×500 in your design tool            |
| Screenshots    | Use the in-app screenshots — capture from a Pixel emulator |
| Privacy policy | (required) host one and link it                |

### Updating after a code change

```bash
# After editing index.html or anything else
npx cap sync android
npx cap open android       # then build AAB in Android Studio
```

---

## 5. iOS (via Capacitor)

```bash
npx cap add ios
npx cap sync ios
npx cap open ios   # opens Xcode
```

Edit `ios/App/App/Info.plist` to add usage strings:

```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>Suplaykart Staff uses your location to verify you punch in/out within the store geofence.</string>
<key>NSCameraUsageDescription</key>
<string>Take a profile photo for your staff card.</string>
<key>NSPhotoLibraryUsageDescription</key>
<string>Choose a profile photo from your photo library.</string>
```

Build → Archive → Distribute via App Store Connect.

---

## 6. Custom domain + HTTPS

On Vercel:

1. Project → Settings → Domains → Add `staff.suplaykart.com`.
2. Add the CNAME record at your DNS provider (Vercel shows you exactly what).
3. HTTPS auto-provisions via Let's Encrypt within a minute.
4. Update Supabase Auth → URL Configuration → Site URL = your custom domain.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Service worker not registering | App must be served over `https://` (or `localhost`) |
| `401` on sign-in | User exists in `auth.users` but `profiles` row missing — re-run the `handle_new_user` trigger from `schema.sql` |
| `RLS violation` on insert | Profile `role` isn't `admin` / `manager` for that action |
| Realtime updates don't fire | Tables not in `supabase_realtime` publication — re-run bottom of `schema.sql` |
| Avatars upload but URL is null | `avatars` bucket not public — re-run storage section of `schema.sql` |
| Capacitor build fails on `keystore` | Path in `key.properties` is wrong — must be **relative to `android/app/build.gradle`** |
| iOS won't load remote URL | `limitsNavigationsToAppBoundDomains: true` is set — list your domains in `WKAppBoundDomains` in Info.plist |

---

Powered by **ALLBEE SOLUTIONS**.
