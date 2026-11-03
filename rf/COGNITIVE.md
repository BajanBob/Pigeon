# Einstein Cognitive Engine — AI-driven link & propagation

*AI-assisted (Claude). Transparent and explainable — every decision shows its reasons.*

Einstein senses its **operational theatre** — the stations and sounding beacons it
actually hears — and adapts autonomously. "AI-driven" here means a cognitive controller
that **classifies propagation, maps open directions, and throttles the modem** to hold a
link, with a readable justification for each decision. It is a heuristic engine grounded
in propagation physics, **not** a black box and not a guarantee.

Files: `rf/einstein_cognitive.py` (engine) and `rf/einstein_beacon.py` (hail + negotiate +
chat); the same logic is ported to the app's **AI** tab.

## 1. Propagation classification (per heard station)

From each spot (callsign, grid, frequency, SNR, time, beacon?) the engine computes the
great-circle distance and bearing from your grid, the band, the UTC hour and the path
geometry, and picks the most likely mode with a confidence and the evidence:

| Mode | When Einstein proposes it |
|---|---|
| **F2** | HF, > 2500 km classic skip (and 6 m long-haul at solar max) |
| **Sporadic-E** | 6 m, 800–2300 km single-hop window (2 m more rarely) |
| **TEP** (trans-equatorial) | VHF, path crosses the geomagnetic equator, N–S, 3000–8000 km, evening, low mid-latitude |
| **Tropo-duct** | VHF/UHF, ≤ ~2000 km with workable SNR (ties into the SSP duct model) |
| **Tropo-scatter** | VHF/UHF, 300–2000 km, always weakly present |
| **Meteor-scatter** | VHF, 400–2300 km bursts |
| **Ground-wave / LOS** | short paths |
| **Beyond normal modes** | VHF/UHF > 2300 km — flagged honestly as exceptional-only |

TEP matters here specifically because Barbados sits near the geomagnetic equator — the
engine will surface N–S trans-equatorial openings that a generic logger would miss.

## 2. Direction analysis

Spots are binned into 8 compass sectors; each open sector reports its dominant mode,
confidence, maximum worked distance and the stations that define it — a quick read of
**which way the band is open and by what mechanism**.

## 3. Link adaptation (throttle up / down)

A ladder maps measured SNR (minus a safety margin) to the fastest modem profile it can
carry, using the modem's own measured thresholds:

| Rung | needs | rate |
|---|---|---|
| STANDARD (r=1/2 QPSK) | ~2 dB | 0.56 kbps |
| PRO (16-QAM HF) | ~10 dB | 2.7 kbps |
| PRO_VHF (64-QAM FM) | ~25 dB | ~9 kbps |

PRO_VHF is offered only on VHF/UHF FM. The engine throttles **up** when SNR rises and
**down** when it falls.

## 4. Redundancy / failover

Watching the recent SNR trend, the engine decides: **hold** (stable), **throttle up**
(rising > 6 dB), **throttle down** (falling fast), or **failover** — when SNR drops below
the decode floor it drops to the most robust profile and **re-hails by beacon**.

## 5. Einstein Beacon — hailing, negotiation, chat

- **Beacon frame** (`EB1`): callsign + grid + capability flags (which profiles the
  station supports) + the SNR it heard you at, as a **CQ** or addressed to a callsign.
  Clear text, zlib-compressed (reversible, not a cipher). Sent on VHF/HF digital
  frequencies.
- **Negotiation**: on contact, both stations pick the **fastest profile they both
  support** that the measured SNR allows — cognitive link adaptation across the link.
- **Chat**: a live, bidirectional clear-text chat over the agreed profile, with speed
  renegotiated on the fly if the link changes.

Self-test (`python3 einstein_beacon.py`) hails CQ, negotiates (correctly falling back to
PRO when the far station lacks the VHF profile), and round-trips chat messages.

## 6. Setup

The app's **Settings → Station setup** requires a valid **grid square** (the whole
engine depends on it) and auto-detects **this computer's IP** (best-effort WebRTC,
editable) plus the Einstein modem port, for the desktop link and modem networking.

## Honesty & legal

Classifications are best-effort estimates from limited spot data and simplified physics —
a planning aid, not a promise, and each one shows the reasoning so you can judge it. All
beacon/chat traffic is **clear text** on bands you are licensed for; Einstein Beacon is
Einstein-native and not interoperable with other beacon systems.
