#!/usr/bin/env python3
"""
HOMER  —  low-SNR amateur position mode  (AVIAN codec, AI-assisted design)
==========================================================================
HOMER (homing-pigeon weak-signal position beacon), running the AVIAN codec
(Adaptive Viterbi / AI Narrowband). Formerly "PigeonFSK-2"; the name is kept in
the module for import stability. A second-generation Pigeon RF mode built to pull
a position beacon out of the noise far below where PigeonFSK-1 (Hamming) gives up.
Clear text (ham-legal). "AI-assisted" is the accurate label — the design was done
by the AI here; the specific serving model version is not asserted.

Signal-processing stack
  * narrow 16-FSK, ~3.9 baud, tones on exact FFT bins (~1000-1059 Hz, ~59 Hz wide)
  * NON-COHERENT SOFT-DECISION detection: each symbol's 16 tone powers become
    4 soft bit metrics (max-log), not hard decisions
  * convolutional FEC r=1/2, K=7 (G=171,133 octal) with a soft-input Viterbi
    decoder  (~5 dB coding gain over uncoded)
  * block interleaving against HF fading, CRC-16/CCITT as the final gate
  * Costas-style known sync array for acquisition well below 0 dB SNR

SNR is reported in the amateur 2500 Hz reference bandwidth (the same convention
behind FT8's "-21 dB") so the numbers are comparable to other weak-signal modes.

LEGAL: amateur radio forbids encryption — this is clear text. Internet sharing in
Pigeon stays AES-256; that never touches RF.
"""
import numpy as np, struct

FS      = 12000
SYMLEN  = 3072                 # baud = FS/SYMLEN = 3.906
NTONES  = 16                   # 4 bits/symbol
BIN0    = 256                  # 256 * FS/SYMLEN = 1000.0 Hz
BINHZ   = FS / SYMLEN
TONE_HZ = [(BIN0 + k) * BINHZ for k in range(NTONES)]
# a 16-symbol Costas-like sync array (distinct tones, good autocorrelation)
SYNC    = [2, 11, 5, 14, 0, 7, 13, 4, 9, 15, 1, 8, 3, 12, 6, 10]
LEAD    = SYMLEN

# ---- convolutional code r=1/2 K=7 + soft Viterbi --------------------------------
K = 7; G = [0o171, 0o133]; NST = 1 << (K - 1)
_nxt = np.zeros((NST, 2), int); _out = np.zeros((NST, 2, 2), int)
for s in range(NST):
    for b in (0, 1):
        reg = (b << (K - 1)) | s
        _out[s, b] = [bin(reg & g).count("1") & 1 for g in G]
        _nxt[s, b] = (s >> 1) | (b << (K - 2))

def conv_encode(bits):
    s = 0; o = []
    for b in list(bits) + [0] * (K - 1):
        o += list(_out[s, b]); s = _nxt[s, b]
    return np.array(o, np.int8)

def viterbi_soft(llr):
    n = len(llr) // 2; INF = 1e18
    pm = np.full(NST, INF); pm[0] = 0.0
    bp = np.zeros((n, NST), np.int8); bb = np.zeros((n, NST), np.int8)
    r = llr.reshape(n, 2)
    for t in range(n):
        npm = np.full(NST, INF)
        for s in range(NST):
            if pm[s] >= INF: continue
            for b in (0, 1):
                ns = _nxt[s, b]; exp = 1 - 2 * _out[s, b]
                m = pm[s] - (r[t, 0] * exp[0] + r[t, 1] * exp[1])
                if m < npm[ns]: npm[ns] = m; bp[t, ns] = s; bb[t, ns] = b
        pm = npm
    s = int(np.argmin(pm)); bits = np.zeros(n, np.int8)
    for t in range(n - 1, -1, -1):
        bits[t] = bb[t, s]; s = bp[t, s]
    return bits[:n - (K - 1)]

# ---- CRC + bit helpers ----------------------------------------------------------
def crc16(d):
    c = 0xFFFF
    for by in d:
        c ^= by << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if (c & 0x8000) else (c << 1) & 0xFFFF
    return c
def _b2bits(bs):
    out = []
    for by in bs: out += [(by >> i) & 1 for i in range(8)]
    return out
def _bits2b(bits):
    bs = bytearray()
    for i in range(0, len(bits) - 7, 8):
        bs.append(sum(bits[i + j] << j for j in range(8)))
    return bytes(bs)

# block interleaver
def _il(bits, w=16):
    n = len(bits); rows = (n + w - 1) // w; pad = list(bits) + [0] * (rows * w - n)
    return [pad[r * w + c] for c in range(w) for r in range(rows)], n
def _dil(vals, n, w=16):
    rows = (n + w - 1) // w; total = rows * w
    vals = list(vals[:total]) + [0.0] * max(0, total - len(vals))
    grid = [0.0] * total; idx = 0
    for c in range(w):
        for r in range(rows):
            grid[r * w + c] = vals[idx]; idx += 1
    return grid[:n]

# ---- framing (FIXED length -> no fragile header symbol) -------------------------
P0 = 23                                    # fixed pre-CRC payload region (bytes)
def _frame_plan():
    info_bits = (P0 + 2) * 8               # payload+CRC bytes -> bits
    ncoded = (info_bits + (K - 1)) * 2     # conv r=1/2 incl. flush
    rows = (ncoded + 15) // 16; il_len = rows * 16
    if il_len % 4: il_len += 4 - il_len % 4
    return ncoded, il_len, il_len // 4
NCODED, IL_LEN, NDATA = _frame_plan()      # all constants — RX knows them

def _payload(call, grid, sym):
    cs = call.upper().encode("ascii")[:12]; gr = grid.encode("ascii")[:8]
    body = bytes([len(cs)]) + cs + bytes([len(gr)]) + gr + bytes([sym & 0xFF])
    body = body + bytes(P0 - len(body))    # zero-pad to the fixed region
    return body + struct.pack(">H", crc16(body))

def build_symbols(call, grid, sym=0x2F):
    coded = conv_encode(_b2bits(_payload(call, grid, sym)))    # len == NCODED
    il, n = _il(list(coded), 16)
    while len(il) % 4: il.append(0)
    data = [il[i] | (il[i+1]<<1) | (il[i+2]<<2) | (il[i+3]<<3) for i in range(0, len(il), 4)]
    return SYNC + data, n

# ---- modulation -----------------------------------------------------------------
def modulate(call, grid, sym=0x2F):
    syms, n = build_symbols(call, grid, sym)
    t = np.arange(SYMLEN) / FS; out = [np.zeros(LEAD)]; ph = 0.0
    for s in syms:
        f = TONE_HZ[s]; out.append(np.sin(2*np.pi*f*t + ph)); ph = (ph + 2*np.pi*f*SYMLEN/FS) % (2*np.pi)
    y = np.concatenate(out); y *= 0.6 / (np.max(np.abs(y)) + 1e-9)
    return y.astype(np.float64)

# ---- demod: powers, soft metrics, sync, decode ----------------------------------
def _powers(x, pos):
    w = x[pos:pos+SYMLEN]
    if len(w) < SYMLEN: w = np.pad(w, (0, SYMLEN-len(w)))
    sp = np.abs(np.fft.rfft(w))**2
    return np.array([sp[BIN0+k] if BIN0+k < len(sp) else 0.0 for k in range(NTONES)])

def _soft_bits(P):                      # 4 soft metrics from 16 tone powers (max-log)
    P = P / (np.mean(P) + 1e-12)
    out = []
    for j in range(4):
        ones = [P[k] for k in range(NTONES) if (k >> j) & 1]
        zeros = [P[k] for k in range(NTONES) if not ((k >> j) & 1)]
        out.append(max(zeros) - max(ones))   # >0 => bit 0 (matches viterbi exp map)
    return out

def _sync_score(x, pos):
    sc = 0.0
    for i, s in enumerate(SYNC):
        P = _powers(x, pos + i*SYMLEN)
        sc += P[s] / (np.sum(P) + 1e-12)
    return sc

def _decode_at(x, start):
    pos = start + len(SYNC)*SYMLEN
    if pos + NDATA*SYMLEN > len(x): return None
    soft = []
    for i in range(NDATA):
        soft += _soft_bits(_powers(x, pos + i*SYMLEN))
    de = _dil(soft[:IL_LEN], NCODED, 16)         # de-interleave soft metrics
    try:
        info = viterbi_soft(np.array(de, float))
    except Exception:
        return None
    data = _bits2b([1 if b else 0 for b in info])
    if len(data) < P0 + 2: return None
    body = data[:P0]
    got = struct.unpack(">H", data[P0:P0+2])[0]
    if crc16(body) != got: return None           # final gate — no false decodes
    try:
        lcs = body[0]; cs = body[1:1+lcs].decode("ascii"); p = 1+lcs
        lgr = body[p]; gr = body[p+1:p+1+lgr].decode("ascii"); p += 1+lgr
        symbol = body[p]
    except Exception:
        return None
    return {"callsign": cs, "grid": gr, "symbol": symbol}

def demodulate(samples, search=None):
    x = np.asarray(samples, float)
    # coarse acquisition: slide the Costas sync array, keep best-scoring starts
    hi = len(x) - (len(SYNC))*SYMLEN
    if search is not None: hi = min(hi, search)
    step = SYMLEN // 4
    cands = []
    for pos in range(0, max(1, hi), step):
        cands.append((_sync_score(x, pos), pos))
    cands.sort(key=lambda c: -c[0])
    # refine the top coarse peaks to sample-ish resolution, then try CRC-gated decode
    tried = set()
    for _, cpos in cands[:12]:
        for off in range(-step, step+1, SYMLEN // 16):
            p = cpos + off
            if p < 0 or p in tried: continue
            tried.add(p)
            r = _decode_at(x, p)
            if r is not None: return r
    return None

# ---- helpers for measuring SNR in the 2500 Hz reference bandwidth ----------------
def add_noise_snr2500(sig, snr_db, rng):
    active = sig[LEAD:]
    psig = np.mean(active**2)
    var = psig * (FS/2) / (2500.0 * 10**(snr_db/10))   # noise power in 2500 Hz ref
    return sig + rng.normal(0, np.sqrt(var), len(sig))

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4 and sys.argv[1] == "tx":
        import wave
        y = modulate(sys.argv[2], sys.argv[3]); pcm = (np.clip(y,-1,1)*32767).astype("<i2")
        with wave.open(sys.argv[4] if len(sys.argv)>4 else "beacon2.wav","wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(FS); w.writeframes(pcm.tobytes())
        print("wrote", len(y)/FS, "s")
    else:
        print("usage: pigeon_rf2.py tx CALL GRID [out.wav]")
