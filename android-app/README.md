# HajiHaz AI Android App

Native Android wrapper for the live HajiHaz AI web app at `https://hajihazai.allbeesolutions.com`.

## Build locally

1. Open [android-app](/Users/hajihaz/Documents/Rkn%20associates/Hostinger%20management/developer/android-app) in Android Studio.
2. Let Gradle sync using Android Studio's bundled JDK.
3. Run `app` on an emulator or real device.

## Release outputs

- Debug APK: `app/build/outputs/apk/debug/`
- Release AAB: `app/build/outputs/bundle/release/`

## Signing

The project is configured to use `keystore/hajihaz-upload.jks` via [keystore.properties](/Users/hajihaz/Documents/Rkn%20associates/Hostinger%20management/developer/android-app/keystore.properties).

## Play Console

Upload the generated `.aab` to the existing Play Console account after:

- adding app screenshots
- filling Data safety
- adding privacy policy
- completing app content declarations
