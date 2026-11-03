# Einstein Modem — adaptive OFDM data modem for HF/VHF

*AI-assisted (Claude). Clear-text, amateur-legal. Two tiers: **Standard** (free,
limited) and **Einstein Pro** (ultra-high-speed, unlocked).*

The Einstein Modem is a software data modem for **messaging and RF email** over an
ordinary SSB radio — the same job VARA does for Winlink, but open, Einstein-native,
and honest about its scope. It modulates an audio-passband OFDM waveform you feed
into the mic/ACC input of any HF or VHF SSB rig; the far end demodulates it back to
bytes. On top of it sits **Einstein Email** (`einstein_email.py`), a compressed,
CRC-protected, ARQ store-and-forward message layer.

> **Honest scope.** This is a genuine, runnable OFDM prototype with measured
> simulation numbers — not a finished product. A production VARA competitor is a
> multi-year effort (real-world multipath, timing/frequency acquisition under QSB,
> interleaving, a mature ARQ state machine, interop testing on dozens of rigs). The
> Einstein Modem is **not** VARA-compatible (VARA is proprietary and closed) and is
> **not** a drop-in Winlink replacement. It is an open waveform you can read, test
> and extend. See the roadmap at the end.

---

## Why two tiers (the VARA model, done openly)

VARA ships free with a speed cap and sells a licence that unlocks full speed. Einstein
mirrors the *shape* of that model but keeps everything clear-text and the throttle
fully visible — there is no DRM and no hidden lock on the air:

| | **Standard (free)** | **Einstein Pro** |
|---|---|---|
| Bandwidth | ~1000 Hz | ~2400 Hz (HF) / wider on VHF FM |
| Constellation | QPSK (2 bits/carrier) | 16-QAM (4 bits/carrier) |
| FEC | conv r=1/2 K=7, soft Viterbi | conv r=1/2 K=7, soft Viterbi |
| Airtime | **governed**: 30 s/over, 120 s per 10 min | unlimited |
| Throughput¹ | ≈ **0.56 kbps** | ≈ **2.7 kbps** |

¹ Measured end-to-end on a 70-byte frame including preamble + FEC overhead (see below).
Real-world payload throughput is lower once ARQ retries and channel fading are included.

The free-tier limit is enforced by a transparent **airtime governor**
(`AirtimeGovernor` in `einstein_modem.py`): it caps continuous over length and total
airtime in a rolling 10-minute window; Pro removes both caps. The governor only
decides *when you may key up* — it never encrypts or obscures anything.

---

## Waveform

- **Sample rate** 8000 Hz, **audio centre** 1500 Hz (fits any SSB passband).
- **OFDM**: 128-point IFFT, subcarrier spacing 62.5 Hz.
  - Standard uses ~16 used carriers (~1 kHz); Pro uses ~38 (~2.4 kHz).
  - **Cyclic prefix** 32 samples (Standard) / 24 (Pro) → guards against delay spread.
- **Pilots**: every 4th (Standard) / 5th (Pro) subcarrier carries a known pilot.
  A leading **all-pilot OFDM symbol** does sync + least-squares channel estimation;
  per-symbol pilots then track residual phase/Doppler drift (zero-forcing equaliser).
- **Constellation**: Gray-coded QPSK / 16-QAM, unit average power.
- **FEC**: the shipping Pigeon-line convolutional code (r=1/2, K=7, polynomials
  171/133 octal) with a **soft-decision Viterbi** decoder fed max-log LLRs from the
  equalised symbols.
- **Framing**: preamble → length-prefixed payload → convolutional tail. Einstein Email
  adds per-block `(index, total, payload, CRC-16)` framing for selective ARQ.

## Measured — clean channel (AWGN-free round trip)

```
Standard (free) : clean decode OK | 70 B in 1.00 s -> 560 bps,  BW 1000 Hz, QPSK
Einstein Pro    : clean decode OK | 70 B in 0.21 s -> 2679 bps, BW 2400 Hz, 16-QAM
```

## Measured — robustness (FER vs SNR)

Frame-error rate (whole coded 64-byte frame) vs per-sample audio SNR, 50 trials/point:

| SNR (dB) | −2 | 0 | 2 | 4 | 6 | 8 | 10 | 12 | 14 |
|---|---|---|---|---|---|---|---|---|---|
| **Standard** AWGN | 0.90 | 0.22 | 0.02 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| **Standard** fading | 1.00 | 0.94 | 0.80 | 0.70 | 0.80 | 0.68 | 0.74 | 0.62 | 0.52 |
| **Pro** AWGN | 1.00 | 1.00 | 1.00 | 1.00 | 0.86 | 0.32 | 0.00 | 0.00 | 0.00 |
| **Pro** fading | 1.00 | 1.00 | 1.00 | 1.00 | 0.92 | 0.68 | 0.36 | 0.20 | 0.22 |

~10% FER thresholds: **Standard ≈ 2 dB AWGN**, **Pro ≈ 10 dB AWGN** (the price of 16-QAM's
4× payload is ~8 dB more SNR, as expected).

> **Honest reading of the fading row.** Under CCIR moderate HF fading this prototype
> has a clear **error floor** — Standard sits around 0.5 FER and Pro around 0.2 even at
> 14 dB. That is expected for a first-cut OFDM with a *single* preamble channel estimate,
> no time interleaving and no bit-loading: a deep fade wipes a whole frame. In practice
> it is the **Einstein Email ARQ layer that carries traffic through fading** — it keeps
> re-sending the blocks that fail (the 30%-loss test below recovered a full message in 5
> rounds). The waveform-level fixes that would actually lift the fading floor —
> **time/frequency interleaving, per-subcarrier bit-loading, and the sequence-model
> equaliser** — are exactly items 1, 2 and the interleaver on the roadmap below. We ship
> the measured truth, not an optimistic claim.

*(Watterson = CCIR 2-path HF fading, ~1 Hz Doppler spread, 2 ms delay. FER = frame
error rate over the whole coded frame; Einstein Email's ARQ recovers the frames that
fail, at the cost of extra rounds.)*

## Measured — messaging + ARQ

```
Einstein Email self-test
  message blob: 166 bytes compressed (zlib, clear-text, reversible — not a cipher)
  round-trip header FROM/TO/SUBJ parsed OK, body OK
  ARQ clean  (PRO) : ok=True  rounds=1  (no retransmits needed)
  ARQ 30%-loss (STD): ok=True rounds=5  (selective retransmit recovered every block)
```

---

## New / innovative features recommended for Einstein Pro

These go beyond what VARA and the other HF modems do today. Items marked **(in code)**
are implemented in this prototype; the rest are the recommended roadmap, in priority
order, each a concrete piece of work rather than a slogan.

1. **Adaptive per-subcarrier bit-loading (water-filling).** Measure SNR per subcarrier
   from the pilots and load more bits onto the clean carriers, fewer onto the carriers
   sitting in a fade or carrier. This is the single biggest real-world throughput win
   on a selective HF channel and is *the* feature that would let Pro genuinely exceed
   VARA on a notched band.
2. **Neural / ML channel equaliser — the Einstein "AI" tribute.** A small sequence
   model (1-D CNN or GRU) trained on pilot-equalised symbols to clean up residual
   inter-carrier interference and fast fading. *Honest note:* our earlier test showed a
   per-symbol MLP does **not** beat max-log on non-coherent FSK — the win only appears
   with a **sequence** model that sees inter-symbol structure, so that is what is
   specified here, not a per-symbol net.
3. **LDPC / fountain codes.** Replace (or layer over) the convolutional FEC with LDPC
   for long frames, and a **rateless fountain code** (LT/Raptor) for ARQ so the TX can
   keep sending fresh parity until the RX has enough — no explicit NAK round-trips.
   *Honest note:* our short-frame LDPC test did **not** beat the conv code at 200 bits;
   the LDPC win needs long frames, which is exactly the RF-email case.
4. **Pilot-aided Doppler/drift tracking (in code).** Per-symbol pilot phase correction
   is implemented; the roadmap extends it to a per-carrier frequency-offset tracker for
   ionospheric Doppler and rig LO drift.
5. **Cross-layer link adaptation.** Feed the ALE Link-Quality-Analysis scores and the
   Einstein evaporation-duct / ocean-scatter prediction back into the modem to
   **auto-pick band, channel and profile** before a path even opens — a propagation-aware
   modem, which no HF data modem does today.
6. **Dynamic bandwidth.** Standard 500 Hz–1 kHz for crowded bands; Pro 2.4 kHz on HF
   and genuinely wideband on VHF FM where the channel allows it.
7. **Compressed, templated messaging (in code).** zlib compression is in the Email
   layer now; the roadmap adds a shared **dictionary** of common ham/traffic phrases
   (callsign formats, QTC/Winlink boilerplate) so short messages compress far harder.
8. **Transparent airtime governor (in code).** The honest, open equivalent of VARA's
   free-tier speed cap — visible, no DRM, Pro removes it.

---

## Files

- `einstein_modem.py` — OFDM modem core (QPSK/16-QAM, pilots, equaliser, FEC), the
  two profiles, and the airtime governor. `python3 einstein_modem.py` self-tests.
- `einstein_email.py` — messaging / RF-email layer: compose, compress, block-frame,
  CRC, and selective ARQ. `python3 einstein_email.py` self-tests.
- `einstein_modem_measure.py` — FER-vs-SNR harness (AWGN + Watterson fading).

## Legal

Everything on the RF path is **clear text**. zlib compression is a published,
reversible, key-less transform (anyone can decode it) and is permitted under amateur
rules; it is **not** encryption. There is no AES, scrambling or obscuring of message
content on the air — ever. (Einstein's *internet* paths, in the companion Pigeon app,
are separately AES-256 and never touch RF.)
