# Einstein / Pigeon — master specifications & recommendations

Durable record of the whole project so nothing is lost. Everything below is in the
repos; measured numbers were produced by running the code (AWGN/fading sims), not
estimated. Credit: **AI-assisted (Claude)** — the serving model version is not asserted.

---

## 1. Complete file inventory

### Einstein repo (`github.com/BajanBob/Einstein`) — the hybrid station app
| File | Purpose |
|---|---|
| `www/index.html` | The app: Dashboard, New entry, Log, **Analyzer** (spectrum+waterfall), **Recorder**, **Repeater** controller, Import (WSJT-X), **Tools** (MMSI/Selcall/ALE), Settings. |
| `electron/main.js` | Electron desktop shell (Windows/Linux). |
| `capacitor.config.json`, `package.json` | Capacitor (Android) + electron-builder config. appId `net.einstein.log`. |
| `resources/icon.*` | Atom/orbits icon. |
| `.github/workflows/build.yml` | Builds Android/Windows/Linux, publishes to release `v1.0.0`. |
| `README.md`, `ROADMAP.md` | Overview + honest phased roadmap. |

### `rf/` — the Pigeon transmitter / RF project (now in Einstein and Pigeon)
| File | Purpose |
|---|---|
| `pigeon_rf.py` | **PigeonFSK-1** — 16-FSK + Hamming(7,4) + interleave + CRC-16. ~−8 dB. |
| `pigeon_rf2.py` | **HOMER (AVIAN codec)** — narrow 16-FSK, soft-decision, conv r=1/2 K=7 + soft Viterbi, interleave, CRC, Costas sync. ~−21 dB. |
| `homer_ldpc.py` | LDPC variant of HOMER (measured: does NOT beat conv at 200-bit frame). |
| `rf_station.py` | Station runner — **TX+RX, all modes, HF+VHF**, soundcard, relay push, ALE sound/scan/call. |
| `pigeon_ale.py` | Selcal + Beacon/sounding+LQA + **ALE** auto channel-select + CALL/ACK/LINKED (Barrett-4050-style, clear text). |
| `mmsi.py` | MMSI encode/decode (ITU-R M.585). |
| `selcall.py` | CCIR/ZVEI1/EEA two-tone-sequential + aeronautical SELCAL encode/decode. |
| `ale_channels.py` | International amateur ALE (HFLINK HFN) channel plan. |
| `measure_fading.py` | AWGN + Watterson HF threshold sweeps (on the real decoder). |
| `ocean_scatter.py` | Ocean Bragg-Doppler channel model + HOMER threshold. |
| `drift_discriminator.py` / `.m` | Oscillator-drift removal + sea-Doppler-vs-rig-drift test. |
| `ldpc_compare.py` | Conv-vs-LDPC coding-gain comparison. |
| `neural_receiver_compare.py` | Neural-vs-classical detector (measured; honest result). |
| `pigeonfsk2_model.m` | MATLAB HOMER model (conv/LDPC, AWGN/HF, true soft LLRs). |
| `evap_duct.m` | MATLAB evaporation/surface-duct refractivity model. |
| `neural_receiver.m` | MATLAB Deep Learning Toolbox neural-receiver training scaffold. |
| `RECEIVER_ARCHITECTURE.md` | MATLAB research→deploy computing architecture. |
| `README.md` | RF project documentation + measured numbers. |

### Pigeon repo (`github.com/BajanBob/Pigeon`) — the location-sharing app
| File | Purpose |
|---|---|
| `www/index.html` | Pigeon app: compass, map, live location sharing, **two-way video call**, **the Door** (paired Pigeon Codes), ham-RF map layer. |
| `relay/worker.js` | Cloudflare Worker — signalling (get/put mailbox, **no KV list**), `/ice`, `/where`, `/rf` board, serves the app. |
| `einstein/**` | Earlier in-Pigeon copy of Einstein (now has its own repo). |

---

## 2. Waveform specifications

### PigeonFSK-1
- 12 kHz sample rate, 1024 samples/symbol → **11.72 baud**, 16-FSK (4 bits/sym).
- Hamming(7,4) FEC, block interleave, CRC-16/CCITT, AGC preamble + 8-sym sync.
- Payload: `[len]callsign[len]grid[symbol]`. Beacon ~5–7 s. Threshold ~**−8 dB**.

### HOMER (AVIAN codec)
- 12 kHz, **3072 samples/symbol → 3.906 baud**, 16-FSK; tones on exact FFT bins
  from 1000 Hz, ~59 Hz spacing (~190 Hz occupied).
- **Non-coherent soft-decision**: 16 tone powers → 4 max-log soft bit metrics.
- **Convolutional FEC r=1/2, K=7, G=(171,133) octal**, **soft-input Viterbi**.
- Block interleave (w=16), CRC-16/CCITT final gate, **16-symbol Costas sync**.
- **Fixed-length frame** (23-byte payload + 2-byte CRC = 200 info bits; no length
  header — the fix that stopped low-SNR crashes). Beacon ~31 s.
- SNR reported in the **2500 Hz reference bandwidth** (FT8 convention).

---

## 3. Measured performance (2500 Hz ref, 50% frame decode)

| Channel | HOMER threshold |
|---|---|
| AWGN | **≈ −21 dB** (100% to −20, ~60% at −21, 0% at −22) |
| HF Watterson — moderate (0.5 Hz Doppler) | ≈ −18 dB |
| HF Watterson — poor (1.0 Hz Doppler) | ≈ −16 dB |
| Ocean scatter — HF (calm) | ≈ −18 dB |
| Ocean scatter — 2 m (moderate sea) | ≈ −12 dB |
| False decodes from pure noise | 0 |

- **LDPC**: short rate-1/2 LDPC + min-sum does **not** beat conv+Viterbi at the 200-bit
  frame (~0.5 dB worse in the waveform). Conv stays the shipping AVIAN code. Real gain
  needs longer frame / irregular H (e.g. FT8 LDPC(174,91)) / sum-product.
- **Neural receiver**: a per-symbol MLP does **not** beat the classical max-log rule
  (max-log is near-optimal for non-coherent FSK). Needs a **sequence model** (correlated
  fading/drift/impulsive noise) to win.
- **Drift discriminator**: recovers rig drift to ~0.01 Hz/s; flags sea Doppler
  (Bragg score 30–40) vs rig drift (~0.4).

### Ocean Bragg Doppler by band (first-order, deep water)
14 MHz 0.38 Hz · 50 MHz 0.72 · 144 MHz 1.22 · 222 MHz 1.52 · 432 MHz 2.12 Hz.

---

## 4. Protocols

- **ALE (Pigeon-native)**: SOUND/CALL/ACK/LINKED frames over HOMER; 4-char Selcal
  addresses; LQA table from sounding SNR; call picks the best channel. CLEAR TEXT.
  **NOT** MIL-STD-188-141 2G ALE interoperable (that needs the standard 8-FSK ALE
  waveform + Golay FEC) — a separate future build.
- **Selcall tone systems**: CCIR (100 ms), ZVEI1 (70 ms), EEA (40 ms), repeat-tone for
  adjacent equal digits; aeronautical SELCAL (ARINC 16-tone A–S, dual-tone pairs).
- **MMSI (ITU-R M.585)**: ship / 0=group / 00=coast / 111=SAR aircraft / 99=AtoN /
  98=craft / 8=handheld; MID→country.
- **International ALE channels**: HFLINK HFN, 160 m–70 cm (USB kHz), region-dependent.

---

## 5. Propagation intelligence (Einstein)

- **Evaporation / surface duct**: from SST, air temp, humidity, pressure → specific-
  humidity deficit, air-sea ΔT, modified-refractivity gradient, **evaporation duct
  height**, and a Low/Moderate/High ducting likelihood (evap duct over warm sea;
  surface inversion when warm air over cooler sea). Predicts VHF/UHF over-water openings.
- **Sea-Doppler vs rig-drift classifier**: measured offset − configured rig reference
  drift, tested against the band Bragg fB → "sea Doppler" or "rig drift". Needs a
  GPSDO/OCXO so rig drift ≪ fB.
- **Grid DX**: great-circle distance + bearing from Maidenhead grids.

---

## 6. Receiver computing architecture (MATLAB)
Two-tier: **Tier-1 research/training on GPU** (Communications/DSP/Deep Learning/Parallel
toolboxes; SDR capture + synthetic channels) → **export** (MATLAB Coder C / GPU Coder
CUDA / `exportONNXNetwork` → Python onnxruntime) → **Tier-3 real-time station decoder**
beside WSJT-X/Einstein. Edge: multi-core CPU, or Jetson Orin for a neural RX. Discipline
the clock (GPSDO/OCXO). Sweet spot: one GPU + ONNX-to-Python on the station PC.

---

## 7. Build & deploy
- **Einstein**: own repo, `.github/workflows/build.yml` → Android APK, Windows NSIS exe,
  Linux AppImage + deb → release `v1.0.0`. Publishes on every push.
- **Pigeon**: `build.yml` (apk/ios/win/linux) + `einstein.yml`; relay is a Cloudflare
  Worker the user deploys (get/put mailbox signalling — never KV `list`).
- CAT: **Hamlib rigctld** — IC-9100/7300/7610/705/905, FT-991A/710/dx10, FTM-500D/300D,
  TS-590SG/890S, most 2020-era rigs.

---

## 8. Recommendations / roadmap (honest)
1. **Desktop helper** (Windows/Linux, Electron Node): rigctld CAT+PTT, WSJT-X UDP decode
   capture, PSK Reporter spotting, **crossband keying**, marine-weather auto-fill.
2. **SDR dual-band RX** (RTL-SDR/Pluto/USRP): true VHF+HF receive feeding the analyzer.
3. **OSM waveform**: VHF ocean-scatter mode — wider tones, per-symbol Doppler/Bragg
   tracking (HOMER loses ~8 dB at 2 m ocean scatter; a dedicated mode recovers it).
4. **Sequence-model neural receiver**: the genuine AI gain (train in MATLAB → ONNX).
5. **Interoperable MIL-STD-188-141 2G ALE** if you want to talk to real Barrett radios.
6. **Stronger FEC**: FT8-style LDPC(174,91) + sum-product for a longer-frame mode.

## 8a. Einstein Modem & Email (data layer) — see `rf/MODEM.md`
- **Einstein Modem** (`rf/einstein_modem.py`): adaptive OFDM, 8 kHz / 1500 Hz audio,
  128-pt IFFT (62.5 Hz spacing), pilot-aided LS channel estimate + zero-forcing
  equaliser, Gray QPSK/16-QAM, conv r=1/2 K=7 soft-Viterbi FEC. Two tiers —
  **Standard** (QPSK ~1 kHz, ≈0.56 kbps, airtime-governed) and **Einstein Pro**
  (16-QAM ~2.4 kHz, ≈2.7 kbps, unlimited).
- **Measured** (50 trials/pt): ~10% FER at **2 dB** (Standard, AWGN) / **10 dB** (Pro,
  AWGN). Under CCIR moderate HF fading both show an error floor (Std ~0.5, Pro ~0.2 at
  14 dB) — honest first-cut limitation; **ARQ** carries traffic through it. Roadmap
  fixes: time/freq interleaving, per-subcarrier bit-loading, sequence-model equaliser.
- **Einstein Email** (`rf/einstein_email.py`): compose → zlib (reversible, clear-text,
  not a cipher) → CRC-16 block framing → selective **ARQ** (recovered a full message
  through 30% frame loss in 5 rounds). Callsign/Selcall addressing.
- **Recommended innovations** (full list in MODEM.md): adaptive bit-loading, sequence-
  model neural equaliser (the AI tribute), LDPC/fountain codes, cross-layer link
  adaptation using ALE LQA + duct/ocean-scatter prediction, dynamic bandwidth,
  templated-dictionary compression, transparent airtime governor.
- **Scope:** a runnable OFDM prototype with measured sim numbers — **not** VARA-
  interoperable (VARA is proprietary) and **not** a Winlink drop-in.

## 8b. SSP — Sea Scatter Propagation analysis & mode — see `rf/SSP.md`
- **`rf/ssp_predict.py`** + in-app **SSP tab**: over-water 2 m/70 cm path analysis between
  two Maidenhead grids. Aggregates marine weather (SST, air temp, RH, pressure, wind) at
  ~11 waypoints along the great-circle path (live Open-Meteo, no key; manual fallback),
  computes evaporation-duct height M(z), surface-inversion strength, duct-continuity
  fraction (weakest-link) and sea-Bragg Doppler, and scores P(workable) with a transparent
  **logistic model** over those features + a hard **physical ceiling** (2 m ≈ 4000 km,
  70 cm ≈ 3000 km).
- **Honest by construction:** ≤1000 mi warm-sea ducting scores realistically (e.g. 700 km
  2 m ≈ 71% LIKELY); ≤3000 mi is the extreme edge; ≤6000 mi and beyond return NOT SUPPORTED
  (shown for completeness). Output: on-screen pop-up, optional email, or WhatsApp.
- Logged as mode "SSP — Sea Scatter (exp)".

## 8c. Cognitive engine + Einstein Beacon — see `rf/COGNITIVE.md`
- **`rf/einstein_cognitive.py`** + in-app **AI tab**: ingests heard-station/beacon spots,
  classifies each path (F2 / Sporadic-E / Tropo-duct / **TEP** / tropo-scatter / meteor /
  ground-wave) with confidence + evidence, maps open compass sectors, and performs
  link adaptation (throttle up/down across STANDARD→PRO→PRO_VHF by measured SNR) with
  redundancy/failover on SNR-trend. Transparent heuristic grounded in propagation physics.
- **`rf/einstein_beacon.py`**: Einstein Beacon (`EB1`) hailing frame (callsign + grid +
  capability mask + heard-SNR, CQ or addressed), capability/SNR **negotiation** (fastest
  profile both stations support that the link allows), and a live clear-text **chat** over
  the agreed profile. Self-tested round-trip (hail → negotiate → bidirectional chat).
- **Setup:** app requires a valid grid square and auto-detects this computer's IP
  (best-effort WebRTC, editable) + Einstein modem port.

## 9. Legal
Amateur radio forbids **encryption** — all RF (PigeonFSK/HOMER/ALE/Selcall and the
Einstein Modem/Email/Beacon/Chat) is **clear text**; zlib compression is reversible and key-less
(permitted, not a cipher). Pigeon's internet sharing is AES-256 and never touches RF.
Transmit only where licensed; identify; respect band plans; a crossband repeater may
need an automatic-station authorisation.
