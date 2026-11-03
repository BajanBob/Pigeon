# Einstein — hybrid weak-signal station: analysis · propagation · RX/TX

A cross-platform (Android / Windows / Linux) **hybrid amateur-radio station tool**, in
tribute to Albert Einstein. Einstein is an **honest** companion: it works *alongside*
WSJT-X and Hamlib rather than re-implementing their decoders, and it is clear about
what is software vs what needs radio hardware.

## What it does today (every platform)
- **Signal analyzer** — live **spectrum + waterfall** of the rig's audio (SSB passband),
  with peak tone, level and estimated SNR.
- **Audio recorder** — record off-air audio to a file for later decode / QSL / analysis.
- **Crossband repeater controller** — VOX-threshold RX monitor that decides when to key
  the TX radio (the brains of a VHF↔HF / 2 m↔70 cm crossband repeat); keying itself is
  driven by the desktop helper over Hamlib PTT (two radios / dual-band rig required).
- **Propagation probing & logging** — UTC log with band, mode, grid DX (distance +
  bearing), SNR, frequency drift; **SST → evaporation-duct / inversion prediction**;
  **sea-Doppler vs rig-drift** classifier (ocean-scatter research). WSJT-X decode import,
  dashboard, ADIF/CSV export.
- **Tools** — **MMSI** decoder (ITU-R M.585), **Selcall** tone tables (CCIR/ZVEI1/EEA +
  aeronautical SELCAL), and the international **ALE** channel plan (HFLINK HFN).
- **AI — Cognitive engine** — Einstein senses the stations and sounding beacons it hears
  and decides, with readable reasons: it classifies each path (**F2 / Sporadic-E /
  Tropo-duct / TEP / tropo-scatter / meteor / ground-wave**), maps which directions are
  open, and throttles the modem FEC/speed up or down with redundancy failover. Hail other
  stations with the **Einstein Beacon** (callsign + grid + capabilities, CQ or addressed)
  on VHF/HF digital, then the radios **negotiate the fastest mutually-supported modem** and
  open a live clear-text **chat**. Transparent, not a black box. Spec: `rf/COGNITIVE.md`.
- **SSP — Sea Scatter Propagation** — AI-assisted over-water 2 m/70 cm path analysis.
  Pick two grid squares; Einstein aggregates the marine-weather variables (SST, air temp,
  humidity, pressure, wind) along the great-circle path from live data, computes
  evaporation-duct height, duct continuity and sea-Bragg scatter, and predicts a
  workable-path likelihood by distance band (≤1000/≤3000/≤6000 mi / beyond). Results go
  to an on-screen pop-up, an optional email, or WhatsApp. **Honest + physics-capped:**
  long bands read near zero because 2 m/70 cm do not propagate that far over sea. Logged
  as a mode. Spec: `rf/SSP.md`.
- **Einstein Email & Modem** — clear-text RF email / messaging over SSB, carried by the
  built-in **Einstein Modem** (adaptive OFDM). Two tiers: **Standard** (free, QPSK ~1 kHz,
  airtime-governed) and **Einstein Pro** (ultra-high-speed, 16-QAM ~2.4 kHz, unlocked).
  Compressed, CRC-protected, selective-ARQ. Compose in-app; modulate/decode with the
  `rf/` tools. Full spec, measured numbers and recommended innovations in `rf/MODEM.md`.
  *Not VARA-compatible, not a Winlink drop-in — an open, honest, Einstein-native modem.*
- **Radio / CAT & standalone station engine** — Einstein stands on its own on a PC/Pi:
  a native **soundcard audio pipe** (capture rig audio for the analyzer, SSP and the
  drift/sea-Doppler classifier; play modem/beacon audio to TX), native **PTT/CAT**
  (VOX, serial RTS/DTR, CM108 GPIO, Hamlib rigctld, Icom CI-V, Yaesu CAT), the
  **AFSK1200 / 300-baud / Robust 8-FSK codecs**, and a **per-model radio preset** table
  for popular 2020-era rigs (IC-9100, IC-705/9700/7100/7300/7610, FT-991A/710/FTDX10,
  TS-590/890, Xiegu, HTs…). The app's **Settings → Radio / CAT** panel auto-fills the
  CI-V address, baud and PTT from the model you pick. This is **additive** to the
  in-app WebAudio analyzer, which still works on every platform. Run it with
  `python3 rf/einstein_station.py`. Spec: `rf/RADIOS.md`.

## The hybrid vision (roadmap)
See `ROADMAP.md`. The headline: a dual-band **VHF/HF** station assistant that
**receives** (SDR + analysis), **probes propagation** (beacons + duct/ocean-scatter
intelligence), **transmits** (the Pigeon HOMER/AVIAN modes + beacons), and can act as a
**crossband repeater** — with a desktop helper for the real-time radio I/O (rigctld CAT,
WSJT-X UDP, PSK Reporter, PTT). Decoders for the established modes stay with WSJT-X;
Einstein is the connective analysis/logging/control layer plus the original Pigeon-line
waveforms.

## Radios (native CAT + Hamlib)
IC-9100 / IC-7300 / IC-7610 / IC-705 / IC-9700 / IC-7100, FT-991A / FT-710 / FTDX10 /
FTDX101, FTM-500D / FTM-300D, TS-590SG / TS-890S, Xiegu X6100 / G90, and HTs via AIOC —
with tested CI-V addresses, CAT baud rates and PTT wiring built in (`rf/einstein_radios.py`,
and the **Settings → Radio / CAT** panel). Any other radio works via Hamlib `rigctld`.
Full reference and the standalone station engine: `rf/RADIOS.md`.


## Platforms & downloads (release v1.0.0)
- **Android** `Einstein.apk` · **iOS** `Einstein-iPhone-unsigned.ipa` (sideload) · **Windows** `.exe`
- **Linux (PC)** x64 AppImage + deb · **Raspberry Pi** arm64 + armv7l AppImage + deb
- **SDR / RF tools** `einstein-sdr-rf-tools.tar.gz` — the `rf/` Python tools (HOMER TX/RX, ALE/Selcall/MMSI, measurements) to run on any Python 3 host (PC or Pi) with an SDR or soundcard. `pip install -r requirements.txt`.

## Build
Pushes build Android/Windows/Linux and publish to the `v1.0.0` release. The RF waveforms,
ALE/Selcall and the receiver research live in the companion Pigeon repo's `rf/` folder.

*Honest scope:* SDR reception, live CAT/PTT, crossband keying and WSJT-X UDP capture need
raw device/socket access = the **desktop helper** (next phase). The analyzer, recorder,
repeater logic, logging, propagation intelligence and tools work on every platform now.
