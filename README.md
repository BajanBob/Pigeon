# 🕊️ Pigeon

**Geographic location-awareness navigator** with encrypted, peer-to-peer live location sharing — over the internet, and (via a companion module) over ham-radio RF.

Pigeon reads your phone's own GNSS fix (GPS + GLONASS + Galileo + BeiDou) and sensors to give you your position, Maidenhead grid square, bearing, distance, speed and ETA to any destination, nearby landmarks, height above sea level, and a street/terrain map — with day, night, and red night-vision screens.

One app, three builds from the same code: **Android**, **iOS**, and **Windows**.

---

## Features

### Navigation
- Live position: latitude/longitude, **Maidenhead grid square**, altitude, speed, GPS accuracy
- Destination by grid square, `lat,lon`, or tap-on-map → **bearing, compass heading, great-circle distance, ETA**
- SVG compass: orange North needle + blue destination arrow (uses the phone's magnetometer/gyroscope)
- **Street** and **terrain** maps (OpenStreetMap + OpenTopoMap)
- Nearby landmarks for reference (Overpass)
- **Day / Night / Red** themes — red-on-black for night-vision navigation

### Live location sharing (internet) — fresh, no third-party servers see your data
- Make a **private link**; the person you send it to just taps **Accept** and the app opens straight to the map on your position.
- The sharer chooses whether to add a **live video feed** and/or a **live audio feed**, can toggle each on/off mid-share, and can **stop sharing** at any time.
- Optional **photo** shows as your marker on their map.
- Everything travels **phone-to-phone over WebRTC**, end-to-end **AES-256-GCM** encrypted. A tiny Cloudflare Worker ("relay") only helps the two phones find each other — it holds nothing for more than a few minutes and **cannot read your location, video or audio**.
- Non-ham contacts can also be placed by IP geolocation when GPS isn't available.

### RF sharing (ham radio) — *companion module, in progress*
- For licensed amateur operators: share your position by **Maidenhead grid square over VHF/UHF/HF**, using the same radios and codecs as Tradewind.
- **Clear-text only** — amateur radio prohibits encryption, so RF position beacons are unencrypted grid-square/callsign reports by law. (Internet sharing remains AES-256 encrypted.)
- Runs on **phone + Windows** (Windows drives the radio through a sound-card interface).

---

## Install

Grab the latest build from the [**Releases**](../../releases) page:

| Platform | File | Notes |
|---|---|---|
| **Android** | `Pigeon.apk` | Enable "Install unknown apps" for your browser/files app, then open the APK. |
| **iOS** | `Pigeon-iPhone-unsigned.ipa` | Unsigned — install with your own signing (AltStore/Sideloadly) or a developer account. |
| **Windows** | `Pigeon-Setup-*.exe` | NSIS installer; Windows SmartScreen may warn on an unsigned app — choose *More info → Run anyway*. |

---

## Build it yourself

Builds run automatically in GitHub Actions (`.github/workflows/build.yml`) on every push to `main` and attach to any published release. To build locally:

```bash
npm install

# Android (needs Android SDK + JDK 17)
npx cap add android && node scripts/patch-android.mjs && npx cap sync android
cd android && ./gradlew assembleDebug      # → app/build/outputs/apk/debug/app-debug.apk

# iOS (needs macOS + Xcode)
npx cap add ios && bash scripts/patch-ios.sh && npx cap sync ios
# open ios/App/App.xcworkspace in Xcode to run/sign

# Windows (needs Windows or wine)
npm run dist:win                            # → dist-win/Pigeon Setup *.exe
```

## Deploy the sharing relay (one-time)

Internet sharing needs a signalling relay. Deploy the included Cloudflare Worker:

1. Create a Worker and a **KV namespace**, bind the namespace to the Worker as `SIG`.
2. Paste [`relay/worker.js`](relay/worker.js) as the Worker code and deploy.
3. In Pigeon → the share panel → paste your Worker URL into **Relay URL** and tap **Save relay**. (The relay URL is embedded in every share link, so the people you share with need no setup.)

The relay only passes WebRTC setup messages and approximate IP geolocation; location/video/audio never pass through it.

---

## Privacy & legal

- Pigeon reads your sensors and sends nothing anywhere on its own. Location sharing happens only when **you** make a link, and only to the person you send it to.
- Internet sharing is end-to-end AES-256 encrypted.
- **RF/amateur-radio position sharing is unencrypted by law** and is for licensed operators only. Do not transmit on amateur frequencies without a licence.
- Not a substitute for official or certified navigation equipment.

## License

MIT — see [LICENSE](LICENSE).
