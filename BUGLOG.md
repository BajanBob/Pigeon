# Pigeon — Bug & Operation Log

_Running record of how the app works, the bugs found in testing, their root
causes, and the fixes. Newest entries at the top._

---

## How Pigeon operates (quick reference)

**Pieces**
- **App** (`www/index.html`) — one self-contained page: compass, map, destination,
  live location sharing, and the Plumage "Stealth message" tool.
- **Relay** (`relay/worker.js`) — a Cloudflare Worker + KV namespace (`SIG`). It does
  three jobs: (1) **signalling** — passes the WebRTC offer/answer between the two
  phones so they can find each other; (2) **/ice** — hands out STUN/TURN servers;
  (3) **serves the app** so a share link opens the live map in any browser.
- **Builds** — GitHub Actions turns `www/` into the Android APK, iOS IPA and
  Windows installer.

**What flows where**
- **Setup only** goes through the relay: a short exchange of 2–3 small messages
  (request → offer → answer). Nothing else.
- **Everything live** — your location, the video feed, the audio feed — goes
  **phone-to-phone** over an encrypted WebRTC connection (AES-256, DTLS-SRGP).
  The relay never sees it and can't read it.
- Once the two phones are connected, **the app stops polling the relay entirely.**

**Cloudflare KV free-tier budget (per day, UTC):** reads 100,000 · writes 1,000 ·
deletes 1,000 · **lists 1,000**. Signalling must stay well inside these.

---

## Bugs & fixes

### 2026-11-02 — Feeds stuck on "connecting"; location worked, video/audio didn't
**Symptom:** The viewer saw the sender's location on the map, but video and audio
never arrived — the feed stayed on "connecting…".

**Root causes (two, stacked):**
1. **KV `list` quota exhausted → 429.** The relay called `KV.list()` on *every*
   poll, and both phones polled once a second. The free tier allows only **1,000
   list ops/day** — about 8 minutes of a call. After that every `list` returned
   **429**, so the relay could no longer pass messages. Location sometimes got
   through early and then flowed phone-to-phone, but the media negotiation that
   came later hit the 429 wall. (Confirmed by Cloudflare's own "exceeded daily
   Workers KV free tier limit of 1,000 list operations" email.)
2. **Fragile media renegotiation.** Video/audio were added *after* the viewer
   connected, via a second WebRTC offer over the 1-second polling relay. On mobile
   that renegotiation often never completed.

**Fixes:**
- **Relay: no more `list`.** Signalling now uses a single mailbox key per
  (room, role) read/written with `get`/`put` only — zero list operations.
  _(Requires pasting the updated `relay/worker.js` into Cloudflare and deploying.)_
- **Non-trickle ICE.** Each phone gathers all its network candidates first, then
  sends **one** offer/answer with them baked in. No per-candidate messages → a
  whole call now costs ~3 relay writes instead of dozens.
- **Stop polling once connected.** When the phone-to-phone link is up, relay
  polling stops (location/media are P2P from then on). Polling only resumes if the
  link drops. This cuts relay reads from thousands per call to a handful.
- **Pre-negotiated media lanes.** The first offer always includes a video and an
  audio "lane". Turning a feed on/off just swaps the track (`replaceTrack`) with
  **no renegotiation** — reliable on mobile.
- **Result (verified, two-browser test):** viewer receives location + video +
  audio; toggling video off drops only video with no reconnection.

**Status:** Fixed in the app. **Relay redeploy still required** (see below).

### 2026-11-02 — Video/Audio feed buttons "gone" / did nothing
**Symptom:** Couldn't find the feed controls; tapping them seemed to do nothing.
**Root cause:** The buttons live far down in the "Share my location" card, and the
camera only turned on once a viewer connected — so there was no feedback.
**Fix:** Added a **self-preview** — tapping Video feed shows your own camera
immediately; Audio feed shows a live mic-level meter. Clear permission-blocked
message. Preview and the transmitted stream are the same (one camera open).
**Status:** Fixed.

### 2026-11-02 — App icon
Added a carrier-pigeon launcher icon (Android/iOS) + in-app header + favicon.
**Status:** Done.

### Earlier (pre-2026-11-02) — selected history
- **Share link useless to recipients** (`https://localhost/#view=…`): relay now
  serves the app, so the link opens the live map. **Fixed.**
- **Picture carrier "too small"** in Stealth with large attachments: covers now
  auto-size to the data. **Fixed.**
- **Tap-the-map to pick destination** not obvious: tap anywhere now sets it +
  `invalidateSize()`. **Fixed.**
- **Barbados ZIP not resolving:** Barbados postcodes aren't in OpenStreetMap; the
  field now accepts a town/area/address. **Fixed (data limitation noted).**
- **Real location leaking on VPN:** GPS is satellite (VPN can't change it) and
  WebRTC can leak the real IP; added **Masked** mode + **Hide my IP (relay-only)**
  + configurable TURN. **Fixed / mitigated.**

---

## Known limits & guidance
- **Relay-only / "Hide my IP"** needs a working **TURN** server. The shared free
  TURN can be slow; set your own (metered.ca free tier) in Share → ⚙️ Advanced.
- **KV writes (1,000/day)** now cover ~300 calls/day. Heavy use → Workers Paid ($5/mo).
- **iOS** build is unsigned (sideload/AltStore); App Store needs an Apple account.
- **Diagnostics:** both the sharer and viewer have a "🔧 Connection diagnostics"
  panel showing the live connection steps — the fastest way to see where a call
  stalls.

---

## ⚠️ Action required after this update
The signalling fix is in **`relay/worker.js`** and must be deployed to Cloudflare:
1. Cloudflare dashboard → **Workers & Pages → `pigeon-relay` → Edit code**.
2. Replace everything with the new `relay/worker.js`, click **Deploy**.
3. The KV `list` limit that caused the 429s resets daily at 00:00 UTC, but the new
   worker doesn't use `list` at all — so deploying it **restores service immediately**,
   even before the reset.
