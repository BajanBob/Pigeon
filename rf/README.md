# PigeonFSK — the Pigeon ham-radio RF mode

A new, narrow-band **amateur-radio digital mode** for beaconing your position
(callsign + Maidenhead grid) over **VHF / UHF / HF SSB**, driving the radio from
a Windows PC through a sound-card interface. Decoded stations appear on the
Pigeon map alongside internet users.

This is **Phase 3** of Pigeon. The phone can't key a radio, so — exactly like the
Tradewind / Lobster chain — the **Windows PC does the RF** and the phone shows the
map.

## Why a new mode (improvements over AFSK-1200 / APRS)

Plain packet/APRS sends raw bits with only a frame check — one fade and the whole
packet is lost. PigeonFSK adds real signal processing:

| | AFSK-1200 / APRS | **PigeonFSK** |
|---|---|---|
| Modulation | 2-tone AFSK | **16-tone MFSK** (4 bits/symbol) on exact FFT bins |
| Bandwidth | ~2.4 kHz (FM) | **~190 Hz** — fits an SSB passband, usable on HF |
| Error correction | none | **Hamming(7,4) FEC** — fixes a bit error in every nibble |
| Burst protection | none | **block interleaving** — spreads QSB/static crashes |
| Integrity | FCS | **CRC-16/CCITT** — rejects any frame with residual errors |
| Robustness (measured) | — | **decodes down to ≈ −8 dB SNR**, 0 false decodes from noise |

Measured on the reference decoder: 40/40 correct decodes at −8 dB SNR with AWGN,
and 0/200 false decodes from pure noise (the CRC never passes garbage).

## Legal — clear text only

Amateur radio **prohibits encryption** or any message intended to obscure meaning.
PigeonFSK is therefore **clear text**: callsign and grid go out in the open, like
APRS. Pigeon's **internet** sharing stays AES-256 encrypted end-to-end — that
encryption is **never** applied on RF. Transmit only on bands you are licensed
for, identify per your regulations, and follow band plans. The tools here do not
key PTT on their own; use VOX or your interface's PTT.

## Mode specification

- Sample rate 12 kHz, 1024 samples/symbol → **11.72 baud**, 16-FSK.
- Tones on exact FFT bins 85–100 (≈ 996–1172 Hz), so they are orthogonal.
- Frame: `[len][callsign][len][grid][symbol]` + CRC-16, Hamming(7,4)-coded and
  block-interleaved, preceded by an AGC preamble and an 8-symbol sync word.
- A beacon is ~5–7 s of audio.

## Files

- **`pigeon_rf.py`** — the codec (modulator, demodulator, FEC, CRC, WAV I/O). Pure
  numpy, no other dependencies. Also a CLI: `python pigeon_rf.py tx CALL GRID out.wav` / `rx in.wav`.
- **`rf_station.py`** — the Windows station runner (TX beacon loop + RX decode loop,
  pushes heard stations to the Pigeon relay).

## Setup (Windows + radio)

1. Wire the rig to the PC with a sound-card interface (SignaLink, Digirig, etc.),
   the same hardware Tradewind uses.
2. `pip install numpy sounddevice`
3. Set the interface as the default audio device (or select it in Sound settings).
4. Set your radio to **USB** on a chosen simplex frequency within your band plan.

### Beacon your position
```bash
python rf_station.py tx  8P6ABC GK03ec  --interval 600 --relay https://pigeon-relay.<you>.workers.dev
```
Transmits every 10 minutes. Without `sounddevice` it writes `pigeon_tx.wav` to play
into the rig manually. Use VOX/PTT to key.

### Listen and map heard stations
```bash
python rf_station.py rx  --relay https://pigeon-relay.<you>.workers.dev
```
Every decode prints a JSON line and is pushed to the relay's `/rf` board. In
Pigeon, turn on **Ham RF** on the map to see those operators plotted at their grid
squares (red markers, callsign on tap).

Decode a recording instead of live audio:
```bash
python rf_station.py rx --wav recording.wav
```

## HOMER — the low-SNR mode (AVIAN codec)

**HOMER** (homing-pigeon weak-signal position beacon) runs the **AVIAN codec**
(Adaptive Viterbi / AI Narrowband). It was formerly called PigeonFSK-2; the module
file keeps the old name for import stability. "AI-assisted design" is the accurate
credit — the specific serving model version is not claimed.

`pigeon_rf2.py` is this second-generation waveform for pulling a beacon out of the
noise far below where the Hamming version gives up:

- narrow 16-FSK at ~3.9 baud (~59 Hz wide)
- **non-coherent soft-decision** detection (16 tone powers → 4 soft bit metrics)
- **convolutional FEC r=1/2, K=7** with a **soft-input Viterbi** decoder
- block interleaving + CRC-16, Costas-style sync for low-SNR acquisition

### Measured sensitivity — honest, on the shipping decoder

All numbers are the **50 % frame-decode threshold** in the **2500 Hz reference
bandwidth** (the FT8 convention), measured by `measure_fading.py` against the real
`pigeon_rf2.py` decoder (not a toy), with **0 false decodes from pure noise**:

| Channel | 50 % threshold |
|---|---|
| **AWGN** | **≈ −21 dB** (100 % to −20 dB, ~60 % at −21, 0 % at −22) |
| **HF fading — moderate** (2-path, 1 ms, 0.5 Hz Doppler) | **≈ −18 dB** |
| **HF fading — poor** (2-path, 2 ms, 1.0 Hz Doppler) | **≈ −16 dB** |

So AWGN beats the −18 dB design target and is FT8-class; moderate HF fading still
meets it; poor fading costs a few dB (expected). Cost of the sensitivity: a ~31 s
beacon. (AWGN has no carrier offset; the fading runs are a Watterson-style
two-path Rayleigh channel with a Gaussian Doppler spectrum.)

### FEC coding gain — convolutional vs LDPC (measured)

`ldpc_compare.py` pits the shipping **convolutional r=1/2 K=7** soft-Viterbi code
against a short **rate-1/2 regular (3,6) LDPC** (normalized min-sum), apples-to-
apples on BPSK+AWGN at the same rate and ~200-bit frame:

| Eb/N0 | conv K=7 | LDPC(3,6) |
|---|---|---|
| 2.0 dB | 72 % | 88 % |
| 2.5 dB | 90 % | **100 %** |
| 3.5 dB | 100 % | 100 % |

On that **isolated BPSK channel** LDPC reaches reliable decode ~1 dB sooner. But
**in the actual waveform** (`homer_ldpc.py`, same FSK front-end, conv→LDPC+min-sum)
the picture reverses — measured AWGN threshold:

| SNR / 2500 Hz | conv (shipping) | LDPC(3,6) + min-sum |
|---|---|---|
| −20 dB | 100 % | 100 % |
| −21 dB | ~60 % | 33 % |
| −22 dB | 0 % | 0 % |

So the short LDPC is **~0.5 dB worse** here, not better. Honest takeaway: at a
200-bit frame, convolutional+Viterbi is excellent and hard to beat; LDPC's edge
only appears with a **longer frame, an irregular/optimized H (e.g. FT8's
LDPC(174,91)), or full sum-product** instead of min-sum. **Convolutional r=1/2 K=7
stays the shipping AVIAN code.** Both decoders give 0 false decodes from noise.

### The MATLAB research model

`pigeonfsk2_model.m` (Communications Toolbox) is the **runnable** research version:
selectable `FEC = 'conv' | 'ldpc'` and `CHAN = 'awgn' | 'hf_moderate' | 'hf_poor'`,
**true non-coherent soft LLRs** (per-tone FFT energies, mirroring `_soft_bits`), a
short LDPC with dual-diagonal parity that `ldpcEncoderConfig` accepts, and an
**active ITU-R HF (Watterson) fading channel** via `comm.RayleighChannel`. It
reproduces the Python thresholds above and is the place to prototype a neural
receiver (Deep Learning Toolbox) — the genuine AI-hybrid step.

### Measurement scripts

- **`measure_fading.py`** — AWGN + Watterson HF threshold sweeps on the real decoder.
- **`ldpc_compare.py`** — convolutional-vs-LDPC coding-gain comparison (self-contained LDPC).

## How it fits Pigeon's two location sources

- **Ham operators** → located by **Maidenhead grid over RF**, clear text, shown via
  the relay `/rf` board. (This file.)
- **Non-ham phones** → located by **GPS or IP over the internet**, AES-256
  encrypted peer-to-peer. (The main app + relay signalling.)

The relay must be redeployed with the `/rf` endpoint (included in `relay/worker.js`)
for the map board to work.
