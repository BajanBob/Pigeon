# Einstein — RF Modes Library

A reference of known radio transmission modes (data, voice, image, video) with
their key parameters, the algorithms behind them, and representative MATLAB
code. The machine-readable version is `rf/modes_library.py` (queryable:
`fits(bw_hz)`, `by_category()`, …); runnable MATLAB generators are in
`rf/mode_waveforms.m`. The app's **Tools → RF Modes Library** shows the same
data and flags which modes fit the Analyzer's current span.

Figures are typical values from public specs. Some proprietary modes
(PACTOR III/IV, VARA) are approximate and flagged. All Einstein on-air modes
are **clear text** (zlib compression is reversible, not a cipher).

---

## How much bandwidth can the Analyzer sample at once?

The Analyzer reads the computer's **audio input**, so its instantaneous span is
set by two things, and the smaller one wins:

1. **The soundcard sample rate → Nyquist = rate ÷ 2.**
   - 48 kHz card → **24 kHz** of spectrum possible
   - 96 kHz → 48 kHz · 192 kHz → 96 kHz
   - Einstein's Analyzer displays **0–6 kHz** by default (the SSB passband), at
     an 8192-point FFT → **~5.9 Hz** bin resolution, ~171 ms time resolution.

2. **The radio's receive passband — usually the real limit:**
   - **SSB:** ~**2.4–2.8 kHz** of audio, no matter how fast the soundcard runs.
   - **FM (data port / discriminator):** ~**5–15 kHz**.
   - **SDR IQ / wideband tap:** the full soundcard Nyquist (24–96 kHz).

**What that means for detection:**

| Through… | Instantaneous span | Modes you can see |
|---|---|---|
| A normal **SSB** rig | ~2.7 kHz | **29 of 45** — all CW/RTTY/PSK, every WSJT mode, SSTV, FreeDV, HF packet, PACTOR/VARA-HF, Einstein modems |
| **FM** data port / discriminator | ~5–15 kHz | + AFSK1200, 9600 packet, D-STAR/DMR/C4FM/P25/NXDN/M17, VARA FM, DRM |
| **SDR** audio (48 kHz) | up to 24 kHz | 38 of 45 (everything except wideband SS and video) |
| **SDR** RF front-end | MHz | the rest — **required** for spread spectrum and video |

**Hard physical limit:** the audio path **cannot** sample **spread-spectrum**
(DSSS ≥ ~1 MHz, FHSS ~MHz, LoRa 125–500 kHz) or **video** (fast-scan ATV ~6 MHz,
DATV 0.1–several MHz). Those need an **SDR with that much RF bandwidth** — no
soundcard, and no SSB/FM radio, can present 6 MHz of ATV to the Analyzer. Einstein
is honest about this: the audio Analyzer is a **narrowband** instrument (kHz),
superb for HF/VHF data/voice; wideband and video discovery is an **SDR** job.

> Rule of thumb: if a mode's occupied bandwidth is **≤ your span**, the Analyzer
> can show it; whether you can *decode* it is a separate question (Einstein IDs
> and measures; WSJT-X / fldigi / a DATV receiver decode).

---

## Data & keyboard modes

| Mode | Baud | Bandwidth | Modulation | Coding / algorithm | Threshold |
|---|---|---|---|---|---|
| CW (Morse) | 5–40 WPM | 150 Hz | OOK (A1A) | none | ~ -18 dB |
| RTTY | 45.45 | 300 Hz | FSK 170 Hz | none, Baudot ITA2 | ~ -6 dB |
| PSK31 | 31.25 | 60 Hz | BPSK | Varicode (QPSK adds conv FEC) | ~ -10 dB |
| MFSK16 | 15.625 | 316 Hz | 16-FSK | conv r=1/2 K=7 | ~ -13 dB |
| Olivia 32/1000 | 31.25 | 1 kHz | 32-MFSK | Walsh/Hadamard FEC | ~ -14 dB |
| Contestia | varies | 500 Hz | MFSK | Walsh FEC | ~ -13 dB |
| THOR / DominoEX | varies | 260 Hz | IFK+ MFSK | conv (THOR) | ~ -12 dB |
| Hellschreiber | 122.5 dot/s | 245 Hz | OOK fuzzy | visual redundancy | ~ -10 dB |
| FSQ | varies | 300 Hz | IFK+ 33-tone | none | ~ -12 dB |

## Weak-signal modes (WSJT-X)

| Mode | Baud | Bandwidth | Modulation | Coding | T/R | Threshold |
|---|---|---|---|---|---|---|
| FT8 | 6.25 | 50 Hz | 8-GFSK | LDPC(174,91)+CRC14 | 15 s | **-21 dB** |
| FT4 | 20.833 | 83 Hz | 4-GFSK | LDPC(174,91) | 7.5 s | -18 dB |
| JT65 | 2.69 | 178 Hz | 65-FSK | Reed–Solomon(63,12) | 60 s | -25 dB |
| JT9 | 1.736 | 16 Hz | 9-FSK | conv/LDPC | 60 s | -27 dB |
| WSPR | 1.465 | 6 Hz | 4-FSK | conv K=32 r=1/2 | 110.6 s | **-31 dB** |
| FST4/W | varies | 33 Hz | 4-GFSK | LDPC(240,101) | 15–1800 s | **-40 dB** |
| Q65 | submode | 200 Hz | 65-FSK + sync | Q-ary RS / LDPC | 15–300 s | -28 dB |
| MSK144 | 2000 | 2.5 kHz | offset MSK | LDPC(128,80) | bursts | -8 dB |

Q65 and MSK144 matter for Barbados: **Q65** is excellent for **TEP/ionoscatter**,
MSK144 for meteor scatter.

## Digital voice

| Mode | Symbol rate | Channel BW | Modulation | Vocoder |
|---|---|---|---|---|
| FreeDV 700D/1600/2020 | OFDM | ~1.25 kHz | OFDM QPSK + pilots (LDPC) | Codec2 / LPCNet |
| D-STAR DV | 4800 | 6.25 kHz | GMSK BT=0.5 | AMBE |
| DMR | 4800 (9600 bps) | 12.5 kHz (2-slot TDMA) | 4FSK | AMBE+2 |
| C4FM / Fusion | 4800 | 12.5 kHz | 4FSK | AMBE+2 |
| P25 Ph1/Ph2 | 4800/6000 | 12.5 / 6.25e kHz | C4FM / H-DQPSK | IMBE / AMBE+2 |
| NXDN | 2400/4800 | 6.25/12.5 kHz | 4FSK | AMBE+2 |
| M17 (open) | 4800 | 9 kHz | 4FSK (RRC) | Codec2 3200 |

## Packet / ARQ data

| Mode | Baud | Bandwidth | Modulation | Coding |
|---|---|---|---|---|
| AFSK1200 (Bell 202) | 1200 | 2.6 kHz | AFSK 1200/2200 on FM | AX.25 CRC-16, NRZI/HDLC |
| HF packet 300 | 300 | 500 Hz | AFSK 200 Hz on SSB | CRC-16 |
| 9600 G3RUH | 9600 | 16 kHz | direct FSK | scrambled NRZ, CRC |
| PACTOR-I | 100/200 | 500 Hz | FSK | Huffman + ARQ |
| PACTOR-III* | multi-tone | 2.4 kHz | 2–18 tone DPSK | adaptive FEC+ARQ |
| PACTOR-IV* | adaptive | 2.4 kHz | PSK/QAM OFDM-like | LDPC-class+ARQ |
| VARA HF* | OFDM | 2.3 kHz | adaptive QAM OFDM | adaptive FEC+ARQ |
| VARA FM* | OFDM | 12.5 kHz | OFDM | adaptive FEC+ARQ |
| ARDOP | adaptive | 2.2 kHz | OFDM/4FSK | FEC+ARQ |
| **Einstein Modem** | OFDM | 2.4 kHz (6 kHz PRO-VHF) | QPSK/16/64-QAM OFDM | conv r=1/2 K=7 + Viterbi, zlib, ARQ |
| **Einstein Robust** | 31.25 | 250 Hz | 8-FSK | conv + soft Viterbi, CRC |

\* proprietary; figures approximate.

## Image / fax / broadcast

| Mode | Rate | Bandwidth | Modulation |
|---|---|---|---|
| SSTV | 8–270 s/frame | 2.3 kHz | FM subcarrier 1500–2300 Hz in SSB |
| WEFAX | 120 lpm, IOC 576 | 1.9 kHz | FM 1500–2300 Hz on SSB |
| DRM | audio+data | 4.5–20 kHz | COFDM QAM, xHE-AAC |

## Spread spectrum (SDR front-end required)

| Mode | Spreading | Bandwidth | Notes |
|---|---|---|---|
| DSSS | PN code (Gold/Barker) | ≥ ~1 MHz | gain = chip/bit; 902/2400/5650 MHz |
| FHSS | hop sequence | ~MHz (hop span) | per-hop FSK/PSK |
| LoRa (CSS) | chirp, SF7–12 | 125/250/500 kHz | 33cm/70cm; ~ -20 dB |

## Video (SDR / TV front-end required)

| Mode | Rate | Bandwidth | Modulation | Coding |
|---|---|---|---|---|
| Fast-scan ATV (NTSC/PAL) | 25–30 fps | **6–8 MHz** | AM-VSB or FM | none |
| DATV DVB-S | SR-dependent | ~1.35 × SR | QPSK | Viterbi + Reed–Solomon |
| DATV DVB-S2 (incl. RB-TV) | 66 kS–multi-MS | 0.1–several MHz | QPSK/8PSK/16/32APSK | LDPC + BCH |
| DATV DVB-T | OFDM | 1–8 MHz | COFDM | LDPC/conv + RS |

---

## Algorithms & encoding — the building blocks

- **Line/source coding:** Morse, Baudot ITA2 (5-bit), ASCII, **Varicode**
  (PSK31/MFSK, short codes for common letters), Huffman (PACTOR), online
  compression (PACTOR/VARA), Codec2/AMBE (voice).
- **Error control:** CRC-16 (AX.25), Reed–Solomon (JT65, DVB-S), convolutional
  + Viterbi (WSPR, MFSK, Einstein), **LDPC** (FT8/FT4/FST4/DVB-S2), Golay/Hamming
  (digital voice), Walsh/Hadamard (Olivia), ARQ retransmission (PACTOR/VARA/ARDOP).
- **Modulation families:** OOK (CW/Hell), FSK/MFSK/GFSK (RTTY, WSJT, DMR, M17),
  PSK/DPSK (PSK31, PACTOR-II/III), QAM-OFDM (VARA, DVB-S2, Einstein), MSK
  (MSK144), CSS chirp (LoRa), analog FM/AM-VSB (ATV, SSTV subcarrier).
- **Spread spectrum:** DSSS (multiply by a fast PN code; processing gain =
  chip rate / bit rate), FHSS (hop a narrow carrier over many channels).

## MATLAB

`rf/mode_waveforms.m` has runnable generators for representative modes. Example —
AFSK 1200 (Bell 202):

```matlab
function x = afsk1200(bits, fs)
  baud=1200; mark=1200; space=2200; sps=round(fs/baud);
  phase=0; x=zeros(1,sps*numel(bits)); cur=mark; k=1;
  for b = bits                    % NRZI: 0 toggles tone, 1 keeps it
    if b==0, if cur==mark, cur=space; else, cur=mark; end; end
    for n=1:sps
      phase = phase + 2*pi*cur/fs;    % phase-continuous
      x(k) = sin(phase); k=k+1;
    end
  end
end
```

Weak-signal 8-FSK tone synthesis (FT8/Einstein-Robust style):

```matlab
function x = mfsk_tones(sym, fs, baud, f0, df)   % sym: 0..M-1 tone indices
  sps=round(fs/baud); phase=0; x=zeros(1,sps*numel(sym)); k=1;
  for s = sym
    f = f0 + s*df;                      % tone spacing df = baud for FT8
    for n=1:sps, phase=phase+2*pi*f/fs; x(k)=sin(phase); k=k+1; end
  end
end
```

DSSS spreader (processing gain = numel(pn)):

```matlab
function tx = dsss(bits, pn, sps)
  chips = reshape((2*pn(:)-1) * (2*bits(:).'-1), 1, []);   % BPSK x PN
  tx = repelem(chips, sps);
end
```

See the file for RTTY, PSK31 (Varicode + BPSK), convolutional encoder (171/133),
FM modulator, and a Costas-array preamble generator.
