# AttendAI — Android App

The Android app is the same React UI as the website, packaged with
[Capacitor 8](https://capacitorjs.com/) (`frontend/android`, `frontend/capacitor.config.ts`).
The UI ships inside the APK. The app talks to an AttendAI server that the user chooses on first
launch, so one APK works with any deployment.

## Install (users)

1. Open the repository's **Releases** page and download `AttendAI-1.0.<build>.apk` from the
   release **"AttendAI Android app"** (tag `android-latest`).
2. On an Android 7.0+ phone, open the file and allow installing apps from that source.
3. The app opens on the sign-in screen, already connected to the live deployment
   **https://attendai-gjk1.onrender.com** (shown as **Server: attendai-gjk1.onrender.com**).
4. Sign in. Demo accounts use the password `Demo@2026`.

To use another AttendAI server, tap **Change** next to the server and enter that website's address
(not your email). The app only accepts `https://` addresses and checks `/health` before saving.
Builds are signed with a per-build key until a release keystore is configured, so uninstall an
older AttendAI build before installing a new one.

## What is different from the website

| Area | Website | Android app |
|---|---|---|
| UI | served by the API (same origin) | bundled in the APK (`https://localhost` WebView origin) |
| Auth | httpOnly session cookie | bearer token from `POST /api/auth/login` with `X-AttendAI-Client: mobile`, stored in app-private storage, revoked on sign-out |
| Navigation | top bar (desktop) / bottom tab bar (phones) | bottom tab bar; Android back button navigates back and exits from the home screen |
| CSV downloads | browser download | saved to the app cache and offered through the Android share sheet |
| Screen | – | edge-to-edge with safe-area insets (status bar and gesture area) |

The server must list the app origin in `MOBILE_APP_ORIGINS` (default
`https://localhost,capacitor://localhost`). It is on by default. Set the variable to `""` to
refuse the app.

## Security notes

* The app accepts only `https://` servers. Plain HTTP is allowed solely for `localhost`/`127.0.0.1`
  (device loopback, used for testing with `adb reverse`), in both the app code and the Android
  network security config.
* The session token never reaches browser JavaScript on the website. Only requests carrying the
  mobile client header receive it.
* Android backup and device-transfer are disabled for app data (`allowBackup=false`,
  `data_extraction_rules.xml`), so the token stays on the device.
* Same server-side authorization as the website (students only see their own records, and so on).

## Build pipeline (`.github/workflows/android.yml`)

On every push touching the frontend (and on manual runs):

1. Build the web bundle and `npx cap sync android`. `VITE_DEFAULT_SERVER_URL` sets the server the
   app opens with: the workflow input, else the `ATTENDAI_SERVER_URL` repository variable, else the
   live deployment `https://attendai-gjk1.onrender.com`.
2. Gradle builds a **signed release APK** and a debug APK. Signing uses the repository secrets
   `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and
   `ANDROID_KEY_PASSWORD` when present. Otherwise it uses a key generated for that build only, so
   users must uninstall before installing a newer build.
3. **Emulator smoke test** (Android 15, where edge-to-edge is enforced): installs the debug APK,
   starts a real API with demo data, runs `e2e/android/app-smoke.mjs` through Playwright's Android
   driver (no native action bar above the app, server change, student dashboard, Requests tab,
   hardware back, layout checks, sign-out, admin dashboard and students) and uploads device
   screenshots as the `android-screenshots` artifact.
4. Publishes the release APK as the GitHub Release `android-latest`. The release notes state whether
   the emulator test passed.

Manual run for another server: **Actions → Android app → Run workflow**, then enter the server URL.
The **Live verification** workflow runs the same device test against the live HTTPS deployment.

### Stable signing (recommended before sharing widely)

```bash
keytool -genkeypair -keystore attendai.jks -alias attendai -keyalg RSA -keysize 2048 -validity 10000
base64 -w0 attendai.jks   # paste into the ANDROID_KEYSTORE_BASE64 repository secret
```

Add the passwords and alias as the other three secrets. Keep the keystore safe: losing it means
users must reinstall.

## Local development

```bash
cd frontend
npm run build && npx cap sync android
npx cap open android          # Android Studio (needs the Android SDK)
# or: cd android && ./gradlew assembleDebug
```

App-mode behaviour can be tested in a desktop browser: `e2e/tests/native-app.spec.ts` serves the
bundle from a second origin and makes Capacitor believe it runs on Android.
