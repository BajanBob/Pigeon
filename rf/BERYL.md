# Beryl — spread-spectrum link + ultrasonic link (COMMERCIAL / EmComm only)

Beryl is Einstein's **commercial / EmComm** capability set, named for Hurricane
Beryl. It is **not** an amateur mode and is **band-gated** to licensed
commercial VHF channels (**148–174 MHz**); it refuses amateur frequencies.

It has two parts:

1. **Beryl SS** — direct-sequence spread-spectrum (DSSS) RF waveform
   (`rf/einstein_beryl.py`).
2. **Ultrasonic data-over-sound** — a short-range, RF-free acoustic link
   (`rf/einstein_ultrasound.py`).

## What Beryl does

- **Spread spectrum for processing gain.** Direct-sequence spreading gives
  **anti-jam robustness** and **low-SNR (below-noise) operation**. Processing
  gain = 10·log₁₀(spreading factor). Measured: at a chip SNR of **−9 dB**,
  spreading factor 127 → **0 % BER**, 511 → **0 % BER** (Gp ≈ 21 / 27 dB).
  Processing gain improves robustness; it is not a guarantee of link performance
  (real range depends on antennas, terrain, interference and power).
- **Confidentiality** via **AES-256-GCM** (scrypt-derived key), the same basis
  as the existing commercial mode. Only on commercial channels.
- **Band-gated and ID-required.** 148–174 MHz only; stations identify per their
  licence, exactly as the commercial mode already enforces.
- **Commercial / EmComm only.** It is refused on amateur frequencies; Einstein
  stays clear-text on the amateur bands. Operate only on channels you are
  authorised to use.

## Beryl SS (DSSS) — parameters

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
that are **resistant to jamming** (spread-spectrum processing gain), work at
**low SNR**, are **confidential** (AES), and can also move a key or config
**without any RF at all** (the ultrasonic link, e.g. across a table at a command
post). Beryl provides those — within the law, on licensed channels, with station
ID, and never on the amateur bands.

## Commercial / EmComm compliance

The commercial module is reserved for operation from **148–174 MHz** under the
appropriate licence. The dividing line is simple: **protecting your content and
making your link robust is allowed; hiding that a transmission is happening, or
evading the rules, is not.**

**Allowed (licensed, band-gated, ID'd):**
- AES-256 confidentiality of message content.
- Spread spectrum for anti-jam / low-SNR robustness, operating openly.
- Text chat, voice, data, the ultrasonic link, the VoIP↔RF gateway, EmComm forms.

**Not allowed (even on commercial channels):**
- Concealing the transmission itself — anything meant to be undetectable or
  disguised so a monitor can't tell you are transmitting. (Hiding *content* is
  fine; hiding the *existence* of the signal is not.)
- Operating outside your authorization, or defeating the 148–174 MHz band gate.
- Removing or faking station identification; impersonating another station.
- Jamming or interfering with other licensed users (anti-jam for your own link
  is fine; denying others is not).
- Intercepting communications you are not a party to.

**Operator responsibilities:**
- Confirm your own licence actually permits encryption and the specific mode —
  not all commercial authorizations do.
- Keep the band gate (148–174 MHz) and station ID enabled.
- Follow your national regulator; have any encryption independently reviewed
  before relying on it for sensitive operations.
