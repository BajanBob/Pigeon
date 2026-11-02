#!/usr/bin/env python3
"""
HOMER / AVIAN-codec — LDPC variant of the PigeonFSK-2 waveform.
Same 16-FSK front-end, soft metrics, interleaver, CRC and Costas sync as
pigeon_rf2, but the convolutional FEC is replaced by a short rate-1/2 LDPC
(normalized min-sum). Goal: push the AWGN threshold past -22 dB.

Measured honestly in the 2500 Hz reference bandwidth, against this decoder.
"""
import numpy as np, struct
import pigeon_rf2 as rf
from ldpc_compare import make_regular_ldpc, gf2_systematic, minsum_decode, ldpc_encode

# ---- LDPC sized to the fixed frame: 200 info bits (23B payload + 2B CRC) ----
K_INFO = 200
# pad info to a K the code supports; build n=2*k code
Kc = 200
Nc = 400
_H = make_regular_ldpc(Nc, 3, 6, seed=7)
_G, _perm = gf2_systematic(_H)
assert _G is not None
_Hp = _H[:, _perm]
assert not (_G @ _Hp.T % 2).any()

SYNC = rf.SYNC
NDATA_L = (Nc + 3) // 4            # 4 bits/symbol -> coded symbols

def _il(bits, w=16):
    n = len(bits); rows = (n + w - 1) // w; pad = list(bits) + [0]*(rows*w - n)
    return [pad[r*w + c] for c in range(w) for r in range(rows)], n
def _dil(vals, n, w=16):
    rows = (n + w - 1)//w; total = rows*w
    vals = list(vals[:total]) + [0.0]*max(0, total-len(vals))
    grid = [0.0]*total; idx = 0
    for c in range(w):
        for r in range(rows):
            grid[r*w+c] = vals[idx]; idx += 1
    return grid[:n]

def modulate(call, grid, sym=0x2F):
    body = rf._payload(call, grid, sym)                 # 23B + 2B CRC = 200 bits
    info = np.array(rf._b2bits(body), np.int8)[:K_INFO]
    cw = ldpc_encode(_G, info)                          # 400 coded bits, systematic
    il, n = _il(list(cw), 16)
    while len(il) % 4: il.append(0)
    data = [il[i] | (il[i+1]<<1) | (il[i+2]<<2) | (il[i+3]<<3) for i in range(0, len(il), 4)]
    syms = SYNC + data
    t = np.arange(rf.SYMLEN)/rf.FS; out = [np.zeros(rf.LEAD)]; ph = 0.0
    for s in syms:
        f = rf.TONE_HZ[s]; out.append(np.sin(2*np.pi*f*t + ph)); ph = (ph + 2*np.pi*f*rf.SYMLEN/rf.FS) % (2*np.pi)
    y = np.concatenate(out); y *= 0.6/(np.max(np.abs(y))+1e-9)
    return y.astype(np.float64), n

def _decode_at(x, start, ncoded_il):
    pos = start + len(SYNC)*rf.SYMLEN
    ndata = (ncoded_il + 3)//4
    if pos + ndata*rf.SYMLEN > len(x): return None
    soft = []
    for i in range(ndata):
        soft += rf._soft_bits(rf._powers(x, pos + i*rf.SYMLEN))
    de = _dil(soft[:ncoded_il], Nc, 16)                 # soft metrics, +=>bit0
    llr = np.array(de, float)                            # min-sum wants +=>bit0
    try:
        bits = minsum_decode(llr, _Hp, iters=40)
    except Exception:
        return None
    info = bits[:K_INFO]
    data = rf._bits2b([1 if b else 0 for b in info])
    if len(data) < rf.P0 + 2: return None
    bodyb = data[:rf.P0]; got = struct.unpack(">H", data[rf.P0:rf.P0+2])[0]
    if rf.crc16(bodyb) != got: return None
    try:
        lcs = bodyb[0]; cs = bodyb[1:1+lcs].decode("ascii"); p = 1+lcs
        lgr = bodyb[p]; gr = bodyb[p+1:p+1+lgr].decode("ascii")
    except Exception:
        return None
    return {"callsign": cs, "grid": gr}

def demodulate(samples):
    x = np.asarray(samples, float)
    _, n = modulate("AAAAA", "AA00")                    # to learn il length
    ncoded_il = ((Nc + 15)//16)*16
    hi = len(x) - len(SYNC)*rf.SYMLEN
    step = rf.SYMLEN//4; cands = []
    for pos in range(0, max(1, hi), step):
        cands.append((rf._sync_score(x, pos), pos))
    cands.sort(key=lambda c: -c[0]); tried = set()
    for _, cpos in cands[:12]:
        for off in range(-step, step+1, rf.SYMLEN//16):
            p = cpos + off
            if p < 0 or p in tried: continue
            tried.add(p)
            r = _decode_at(x, p, ncoded_il)
            if r is not None: return r
    return None

if __name__ == "__main__":
    import time; t0 = time.time()
    rng = np.random.default_rng(1)
    print("HOMER/AVIAN LDPC waveform — AWGN threshold (2500 Hz ref)\n")
    for snr in [-20, -21, -22, -23, -24]:
        ok = 0; T = 15
        for _ in range(T):
            sig, _n = modulate("8P6NH", "GK03")
            rx = rf.add_noise_snr2500(sig, snr, rng)
            r = demodulate(rx)
            ok += (r is not None and r["callsign"] == "8P6NH" and r["grid"] == "GK03")
        print(f"  SNR {snr:>4} dB/2500Hz : {ok:2d}/{T}  ({100*ok/T:.0f}%)")
    # false alarm
    fa = 0
    for _ in range(20):
        n = len(modulate("8P6NH","GK03")[0])
        fa += (demodulate(rng.normal(0,1,n)) is not None)
    print(f"\nFalse decodes from noise: {fa}/20")
    print(f"[done in {time.time()-t0:.0f}s]")
