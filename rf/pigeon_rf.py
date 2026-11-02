#!/usr/bin/env python3
"""
PigeonFSK  —  a clear-text amateur-radio position mode for Pigeon
=================================================================
A new narrow-band digital mode for beaconing a station's position (callsign +
Maidenhead grid + a symbol byte) over VHF/UHF/HF SSB, driving the radio through
a sound-card interface on Windows. The phone displays received stations on the
Pigeon map.

It improves on plain AFSK-1200 / APRS, which sends raw bits with only a frame
check and NO error correction:

  * 16-tone MFSK (4 bits/symbol) — orthogonal tones on exact FFT bins, far more
    robust at low SNR than 2-tone AFSK, and only ~190 Hz wide (fits an SSB
    passband, works on HF where APRS can't).
  * Hamming(7,4) forward error correction — every nibble can survive a bit flip,
    so fades and clicks are corrected instead of dropping the whole packet.
  * Block interleaving — spreads burst errors (QSB/static crashes) across many
    code words so the FEC can still fix them.
  * CRC-16/CCITT — rejects any frame that still has residual errors.

LEGAL: Amateur radio prohibits encryption or any message meant to obscure
meaning. PigeonFSK is therefore CLEAR TEXT only — callsign and grid are sent in
the open. (Pigeon's *internet* sharing stays AES-256 encrypted; that encryption
is never used on RF.) Transmit on amateur frequencies only with a valid licence.

Pure-numpy reference implementation: encoder, decoder, and sound-card WAV I/O.
"""

import numpy as np
import struct, wave, io

# ---- channel / modem parameters -------------------------------------------------
FS          = 12000          # sample rate (Hz) — sound-card friendly, fits SSB
SYMLEN      = 1024           # samples per symbol  -> baud = FS/SYMLEN = 11.72 Bd
NTONES      = 16             # 16-FSK -> 4 bits per symbol
BIN0        = 85             # first tone = bin 85  (85 * FS/SYMLEN ≈ 996.1 Hz)
BAUD        = FS / SYMLEN
BINHZ       = FS / SYMLEN
TONE_HZ     = [(BIN0 + k) * BINHZ for k in range(NTONES)]   # ~996 .. 1172 Hz
SYNC_WORD   = [0, 15, 0, 15, 5, 10, 3, 12]   # fixed sync symbol pattern
PREAMBLE    = [0, 15] * 6                      # AGC / timing lead-in
LEAD_SIL    = SYMLEN                           # a symbol of silence up front

# ---------------------------------------------------------------------------------
#  Hamming(7,4) FEC  — corrects any single bit error per 7-bit code word
# ---------------------------------------------------------------------------------
_G = [  # generator: 4 data bits d0..d3 -> 7 bits
    0b1101001, 0b0101010, 0b1001100, 0b0111000
]
def _ham_enc(nib):
    d = [(nib >> i) & 1 for i in range(4)]
    # systematic-ish: p1 p2 d0 p3 d1 d2 d3  (standard Hamming(7,4))
    d0, d1, d2, d3 = d[0], d[1], d[2], d[3]
    p1 = d0 ^ d1 ^ d3
    p2 = d0 ^ d2 ^ d3
    p3 = d1 ^ d2 ^ d3
    return [p1, p2, d0, p3, d1, d2, d3]

def _ham_dec(bits7):
    b = list(bits7)
    p1, p2, c3, p3, c5, c6, c7 = b
    s1 = p1 ^ c3 ^ c5 ^ c7
    s2 = p2 ^ c3 ^ c6 ^ c7
    s3 = p3 ^ c5 ^ c6 ^ c7
    syn = (s3 << 2) | (s2 << 1) | s1
    if syn:                       # flip the indicated bit (1-based position)
        b[syn - 1] ^= 1
    d0, d1, d2, d3 = b[2], b[4], b[5], b[6]
    return d0 | (d1 << 1) | (d2 << 2) | (d3 << 3)

# ---------------------------------------------------------------------------------
#  CRC-16/CCITT-FALSE
# ---------------------------------------------------------------------------------
def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return crc

# ---- bit helpers ----------------------------------------------------------------
def _bytes_to_bits(bs):
    out = []
    for by in bs:
        out += [(by >> i) & 1 for i in range(8)]
    return out

def _bits_to_bytes(bits):
    bs = bytearray()
    for i in range(0, len(bits) - 7, 8):
        by = 0
        for j in range(8):
            by |= bits[i + j] << j
        bs.append(by)
    return bytes(bs)

# ---- block interleaver (spreads bursts) -----------------------------------------
def _interleave(bits, width=7):
    n = len(bits)
    rows = (n + width - 1) // width
    padded = bits + [0] * (rows * width - n)
    out = []
    for c in range(width):
        for r in range(rows):
            out.append(padded[r * width + c])
    return out, n

def _deinterleave(bits, n, width=7):
    rows = (n + width - 1) // width
    total = rows * width
    bits = list(bits[:total]) + [0] * max(0, total - len(bits))
    grid = [0] * total
    idx = 0
    for c in range(width):
        for r in range(rows):
            grid[r * width + c] = bits[idx]; idx += 1
    return grid[:n]

# ---------------------------------------------------------------------------------
#  FRAME:  [len_cs][callsign][len_grid][grid][symbol] + CRC16  -> Hamming -> interleave
# ---------------------------------------------------------------------------------
def build_frame_bits(callsign: str, grid: str, symbol: int = 0x2F):
    cs = callsign.upper().encode("ascii")[:12]
    gr = grid.encode("ascii")[:8]          # preserve Maidenhead case (AB12cd)
    payload = bytes([len(cs)]) + cs + bytes([len(gr)]) + gr + bytes([symbol & 0xFF])
    payload += struct.pack(">H", crc16(payload))
    bits = _bytes_to_bits(payload)
    if len(bits) % 4:
        bits += [0] * (4 - len(bits) % 4)
    coded = []
    for i in range(0, len(bits), 4):
        nib = bits[i] | (bits[i+1] << 1) | (bits[i+2] << 2) | (bits[i+3] << 3)
        coded += _ham_enc(nib)
    il, n = _interleave(coded, width=7)
    return il, n

def parse_frame_bits(coded_il, n):
    coded = _deinterleave(coded_il, n, width=7)
    bits = []
    for i in range(0, len(coded) - 6, 7):
        bits += [(_ham_dec(coded[i:i+7]) >> j) & 1 for j in range(4)]
    data = _bits_to_bytes(bits)
    if len(data) < 4:
        return None
    # find payload by its own length fields
    try:
        lcs = data[0]; cs = data[1:1+lcs].decode("ascii")
        p = 1 + lcs
        lgr = data[p]; gr = data[p+1:p+1+lgr].decode("ascii")
        p = p + 1 + lgr
        symbol = data[p]; p += 1
        got_crc = struct.unpack(">H", data[p:p+2])[0]
    except Exception:
        return None
    if crc16(data[:p]) != got_crc:
        return None
    return {"callsign": cs, "grid": gr, "symbol": symbol}

# ---------------------------------------------------------------------------------
#  MFSK modulator / demodulator
# ---------------------------------------------------------------------------------
def _symbols_from_bits(bits):
    if len(bits) % 4:
        bits = list(bits) + [0] * (4 - len(bits) % 4)
    syms = []
    for i in range(0, len(bits), 4):
        syms.append(bits[i] | (bits[i+1] << 1) | (bits[i+2] << 2) | (bits[i+3] << 3))
    return syms

def _bits_from_symbols(syms):
    bits = []
    for s in syms:
        bits += [(s >> j) & 1 for j in range(4)]
    return bits

def modulate(callsign, grid, symbol=0x2F):
    coded_il, n = build_frame_bits(callsign, grid, symbol)
    data_syms = _symbols_from_bits(coded_il)
    syms = PREAMBLE + SYNC_WORD + [ (n >> 8) & 0xF, n & 0xF, (n >> 4) & 0xF ] + data_syms
    t = np.arange(SYMLEN) / FS
    sig = [np.zeros(LEAD_SIL)]
    phase = 0.0
    for s in syms:
        f = TONE_HZ[s]
        ph = 2 * np.pi * f * t + phase
        sig.append(np.sin(ph).astype(np.float64))
        phase = (phase + 2 * np.pi * f * SYMLEN / FS) % (2 * np.pi)   # phase-continuous
    out = np.concatenate(sig)
    out *= 0.6 / (np.max(np.abs(out)) + 1e-9)
    return out.astype(np.float32)

def _tone_of(window):
    # On-exact-bin MFSK: rectangular window -> orthogonal tones (sinc nulls on the
    # other candidate bins). FFT magnitude at the 16 tone bins, return the strongest.
    sp = np.abs(np.fft.rfft(window))
    mags = [sp[BIN0 + k] if (BIN0 + k) < len(sp) else 0.0 for k in range(NTONES)]
    return int(np.argmax(mags)), max(mags)

def _read_tone(x, pos):
    tone, _ = _tone_of(x[pos:pos + SYMLEN]); return tone

def _try_decode_at(x, start):
    """start = sample index of the first PREAMBLE symbol. Returns dict or None."""
    pre_syms = len(PREAMBLE)
    pos = start + (pre_syms + len(SYNC_WORD)) * SYMLEN
    if pos + 3 * SYMLEN > len(x):
        return None
    h = _read_tone(x, pos); l = _read_tone(x, pos + SYMLEN); m = _read_tone(x, pos + 2 * SYMLEN)
    pos += 3 * SYMLEN
    n = (h << 8) | l | (m << 4)
    if not (0 < n < 20000):
        return None
    ncoded_syms = (n + 3) // 4
    if pos + ncoded_syms * SYMLEN > len(x):
        return None
    syms = [_read_tone(x, pos + k * SYMLEN) for k in range(ncoded_syms)]
    coded_il = _bits_from_symbols(syms)[:n]
    return parse_frame_bits(coded_il, n)          # None unless CRC passes

def demodulate(samples):
    x = np.asarray(samples, dtype=np.float64)
    env = np.convolve(np.abs(x), np.ones(SYMLEN) / SYMLEN, mode="same")
    if np.max(env) <= 0:
        return None
    hits = np.where(env > 0.25 * np.max(env))[0]
    if len(hits) == 0:
        return None
    base = max(0, hits[0] - SYMLEN)
    pre_syms = len(PREAMBLE)
    # score every candidate symbol-start by how well the known SYNC_WORD lines up
    cands = []
    for off in range(0, 2 * SYMLEN + SYMLEN // 2, max(1, SYMLEN // 64)):
        pos = base + off
        if pos + (pre_syms + len(SYNC_WORD)) * SYMLEN > len(x):
            break
        got = [_read_tone(x, pos + (pre_syms + k) * SYMLEN) for k in range(len(SYNC_WORD))]
        score = sum(1 for a, b in zip(got, SYNC_WORD) if a == b)
        if score >= len(SYNC_WORD) - 1:          # near-perfect sync only
            cands.append((score, pos))
    # try best-scoring alignments first; accept the first that passes CRC
    for _, pos in sorted(cands, key=lambda c: -c[0]):
        r = _try_decode_at(x, pos)
        if r is not None:
            return r
    return None

# ---- WAV sound-card I/O ----------------------------------------------------------
def to_wav_bytes(samples):
    pcm = np.clip(samples, -1, 1)
    pcm = (pcm * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(FS)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()

def from_wav_bytes(data):
    with wave.open(io.BytesIO(data), "rb") as w:
        fr = w.getframerate(); n = w.getnframes()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if fr != FS:   # naive resample to FS
        idx = np.linspace(0, len(x) - 1, int(len(x) * FS / fr))
        x = np.interp(idx, np.arange(len(x)), x)
    return x

def transmit(callsign, grid, symbol=0x2F, path=None):
    sig = modulate(callsign, grid, symbol)
    if path:
        with open(path, "wb") as f:
            f.write(to_wav_bytes(sig))
    return sig

def receive(samples_or_path):
    if isinstance(samples_or_path, str):
        with open(samples_or_path, "rb") as f:
            x = from_wav_bytes(f.read())
    else:
        x = samples_or_path
    return demodulate(x)

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4 and sys.argv[1] == "tx":
        transmit(sys.argv[2], sys.argv[3], path=sys.argv[4] if len(sys.argv) > 4 else "beacon.wav")
        print("wrote beacon WAV")
    elif len(sys.argv) >= 3 and sys.argv[1] == "rx":
        print(receive(sys.argv[2]))
    else:
        print("usage: pigeon_rf.py tx CALLSIGN GRID [out.wav] | rx in.wav")
