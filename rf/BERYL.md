# Beryl — LPI spread spectrum + ultrasonic link (COMMERCIAL / EmComm only)

Beryl is Einstein's **commercial / EmComm** capability set, named for Hurricane
Beryl. It is **not** an amateur mode and is **band-gated** to licensed
commercial VHF channels (**148–174 MHz**); it refuses amateur frequencies.

It has two parts:

1. **Beryl LPI** — direct-sequence spread spectrum (DSSS) RF waveform
   (`rf/einstein_beryl.py`).
2. **Ultrasonic data-over-sound** — a short-range, RF-free acoustic link
   (`rf/einstein_ultrasound.py`).

## What Beryl is — and what it is not

**It is:**
- **Low Probability of Intercept (LPI) + anti-jam** by spreading the signal
  **below the noise floor** (processing gain = 10·log₁₀(spreading factor)).
  Measured: at a chip SNR of **−9 dB** (signal under the noise), spreading
  factor 127 → **0 % BER**, 511 → **0 % BER** (Gp ≈ 21 / 27 dB).
- **Confidential** via **AES-256-GCM** (scrypt-derived key), the same basis as
  the existing commercial mode. Only on commercial channels.
- **Band-gated and ID-required:** 148–174 MHz only; stations identify per their
  licence, exactly as the commercial mode already enforces.

**It is NOT:**
- **"Undetectable."** This is the honest line. The **square-root law** of covert
  communication (Bash, Goeckel & Towsley, 2015) shows truly covert throughput
  trends to zero and needs a pre-shared secret key; and **cyclostationary
  feature detection** / energy integration can reveal a structured signal even
  below the noise floor. A determined wideband SIGINT receiver can still detect
  Beryl's energy. LPI means *harder to intercept/jam*, not *invisible*.
- **For amateur use.** Amateur rules forbid obscuring the meaning of a
  transmission, so neither the spreading-for-concealment nor the encryption is
  ever used on ham RF. Einstein stays clear-text on the amateur bands.
- **A licence to hide from regulators.** Operate only on channels you are
  authorised to use, and identify as your licence requires.

## Beryl LPI (DSSS) — parameters

| Item | Value |
|---|---|
| Spreading | direct-sequence, maximal-length PN (m-sequence) code, BPSK chips |
| Spreading factor | configurable (e.g. 31 / 127 / 255 / 511) |
| Processing gain | 10·log₁₀(SF) dB (≈ 15 / 21 / 24 / 27 dB) |
| Carrier (default) | 12 kHz audio sub-carrier, 8 kchip/s (soundcard path) |
| Confidentiality | AES-256-GCM, scrypt KDF (optional, commercial only) |
| Band | **148–174 MHz commercial / EmComm only** (gated) |
| Error check | AES-GCM auth tag; DSSS correlation decision |

API: `pn_code(sf)`, `spread()/despread()`, `modulate()/demodulate()`,
`encrypt()/decrypt()`, `assert_commercial_band(freq_mhz)`,
`processing_gain_db(sf)`. Self-test: `python3 einstein_beryl.py --selftest`.

## Ultrasonic data-over-sound — parameters

| Item | Value |
|---|---|
| Medium | **acoustic** (sound), not RF |
| Band | near-ultrasound **18–22 kHz** (bit0 18.5 kHz, bit1 19.5 kHz, sync 20.5 kHz) |
| Modulation | BFSK, 100 baud default, sync preamble + length + CRC-8 |
| Range | a few metres, line-of-ear |
| Use | RF-free device-to-device transfer: key exchange, config, short messages |
| Caveats | needs ~20 kHz-capable speaker/mic; ~18–19 kHz audible to young ears/animals |

API: `modulate(data)`, `demodulate(audio)`. Self-test:
`python3 einstein_ultrasound.py --selftest` (software round-trip, 3 messages OK).

## Why this fits EmComm

In a disaster or hostile RF environment a licensed EmComm operator wants comms
that are **hard to jam and hard to intercept** (LPI DSSS), **confidential**
(AES), and that can also move a key or config **without any RF at all** (the
ultrasonic link, e.g. across a table at a command post). Beryl provides those —
honestly, within the law, and never on the amateur bands.
