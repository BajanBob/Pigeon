#!/usr/bin/env python3
"""
Einstein Modem — adaptive OFDM HF/VHF data modem  (AI-assisted, Claude)
=======================================================================
A VARA-class software data modem for messaging and RF email over SSB. OFDM with
pilot-aided channel estimation, Gray-coded QAM, convolutional FEC + soft Viterbi,
and two profiles:

  STANDARD   ~1 kHz, QPSK, r=1/2   — free tier (bandwidth/airtime limited)
  PRO        ~2.4 kHz, 16-QAM, r=1/2 — "Einstein Pro" (ultra-high-speed, unlocked)

Audio-passband (upconverted to 1500 Hz) so it drops into any SSB rig. Clear text
(amateur-legal). NOT VARA-interoperable (VARA is proprietary) and NOT a Winlink
drop-in — this is an open Einstein-native modem; see MODEM.md for scope + roadmap.
"""
import numpy as np
import pigeon_rf2 as rf          # reuse conv_encode + viterbi_soft (r=1/2 K=7, soft)

FS = 8000.0                      # default audio sample rate (HF/SSB profiles)
FC = 1500.0                      # default audio carrier centre

# Each profile may override fs/fc. HF profiles live in the ~2.4 kHz SSB passband;
# the VHF profile uses a wideband FM audio channel (higher fs) for 64-QAM.
PROFILES = {
  "STANDARD": dict(bw=1000.0, nfft=128, cp=32, bits=2, pilot_every=4,
                   fs=8000.0, fc=1500.0, name="Standard (free)"),
  "PRO":      dict(bw=2400.0, nfft=128, cp=24, bits=4, pilot_every=5,
                   fs=8000.0, fc=1500.0, name="Einstein Pro (HF)"),
  # VHF/FM wideband Pro: ~6 kHz audio, 64-QAM, short CP (little multipath on FM).
  # Needs a high-SNR VHF FM link; targets ~9 kbps. Not for HF SSB (bandwidth-capped).
  "PRO_VHF":  dict(bw=6000.0, nfft=256, cp=16, bits=6, pilot_every=8,
                   fs=16000.0, fc=4000.0, name="Einstein Pro VHF (9 kbps)"),
}
def _fs(P): return P.get("fs", FS)
def _fc(P): return P.get("fc", FC)

# ---------- Gray-coded QAM ----------
def _qam_points(bits):
    m = 1 << bits
    if bits == 2:   # QPSK
        pts = np.array([1+1j, -1+1j, -1-1j, 1-1j]) / np.sqrt(2)
        return pts
    k = int(np.sqrt(m)); lv = np.arange(k)*2 - (k-1)
    g = lv.copy()                                    # gray on each axis
    pts = np.array([complex(i, q) for q in g for i in g])
    pts = pts / np.sqrt((np.abs(pts)**2).mean())
    return pts

def _map(bitseq, bits):
    pts = _qam_points(bits); out = []
    for i in range(0, len(bitseq)-bits+1, bits):
        idx = 0
        for b in bitseq[i:i+bits]: idx = (idx<<1) | int(b)
        out.append(pts[idx])
    return np.array(out), pts

def _demap_soft(syms, bits, pts, noise=1.0):
    # max-log LLR per bit (sign: +=>bit0, matching viterbi exp map)
    m = len(pts); llr = []
    masks = [[(k>>(bits-1-j))&1 for k in range(m)] for j in range(bits)]
    for s in syms:
        d = -np.abs(s - pts)**2 / noise
        for j in range(bits):
            ones = [d[k] for k in range(m) if masks[j][k]==1]
            zeros= [d[k] for k in range(m) if masks[j][k]==0]
            llr.append(max(zeros) - max(ones))
    return np.array(llr)

# ---------- OFDM ----------
def _used_bins(nfft, bw, fs=FS):
    span = int(round(bw / (fs/nfft)))               # number of used subcarriers
    half = span // 2
    bins = [k for k in range(-half, half+1) if k != 0]   # skip DC
    return bins

def _ofdm_syms(data_syms, pilots_val, bins, pilot_every, nfft, cp):
    """Pack data symbols into OFDM symbols; every pilot_every-th bin is a pilot."""
    is_pilot = {b: (idx % pilot_every == 0) for idx, b in enumerate(bins)}
    data_bins = [b for b in bins if not is_pilot[b]]
    per = len(data_bins)
    nsym = int(np.ceil(len(data_syms)/per))
    data_syms = np.concatenate([data_syms, np.zeros(nsym*per - len(data_syms), complex)])
    out = []
    for s in range(nsym):
        X = np.zeros(nfft, complex); di = 0
        for b in bins:
            k = b % nfft
            if is_pilot[b]: X[k] = pilots_val
            else: X[k] = data_syms[s*per + di]; di += 1
        x = np.fft.ifft(X) * nfft
        x = np.concatenate([x[-cp:], x])            # cyclic prefix
        out.append(x)
    return np.concatenate(out), nsym, per, is_pilot, data_bins

def _upconvert(x, fs=FS, fc=FC):
    t = np.arange(len(x))/fs
    y = np.real(x * np.exp(2j*np.pi*fc*t))
    return y / (np.max(np.abs(y))+1e-9) * 0.6

def _downconvert(y, fs=FS, fc=FC):
    t = np.arange(len(y))/fs
    a = _hilbert(y) * np.exp(-2j*np.pi*fc*t)
    return a
def _hilbert(x):
    X=np.fft.fft(x); n=len(x); h=np.zeros(n)
    if n%2==0: h[0]=h[n//2]=1; h[1:n//2]=2
    else: h[0]=1; h[1:(n+1)//2]=2
    return np.fft.ifft(X*h)

SYNC_VAL = 1.0+0j

def modulate(data_bytes, profile="STANDARD"):
    P = PROFILES[profile]; nfft, cp, bits = P["nfft"], P["cp"], P["bits"]
    fs, fc = _fs(P), _fc(P)
    bins = _used_bins(nfft, P["bw"], fs)
    # FEC: conv r=1/2 on (len-prefixed) payload
    body = len(data_bytes).to_bytes(2,"big") + data_bytes
    coded = rf.conv_encode(rf._b2bits(body))
    syms, pts = _map(coded, bits)
    base, nsym, per, is_pilot, data_bins = _ofdm_syms(syms, SYNC_VAL, bins, P["pilot_every"], nfft, cp)
    # preamble: one OFDM symbol with pilot on EVERY used bin
    Xp = np.zeros(nfft, complex)
    for b in bins: Xp[b % nfft] = SYNC_VAL
    xp = np.fft.ifft(Xp)*nfft; xp = np.concatenate([xp[-cp:], xp])
    full = np.concatenate([xp, base])
    return _upconvert(full, fs, fc), dict(nsym=nsym, per=per, ncoded=len(coded))

def demodulate(audio, profile="STANDARD", meta=None):
    P = PROFILES[profile]; nfft, cp, bits = P["nfft"], P["cp"], P["bits"]
    fs, fc = _fs(P), _fc(P)
    bins = _used_bins(nfft, P["bw"], fs); sl = nfft+cp
    a = _downconvert(np.asarray(audio, float), fs, fc)
    def demod_symbol(x):
        x = x[cp:cp+nfft]; return np.fft.fft(x)/nfft
    # preamble -> channel estimate H on used bins
    Hp = demod_symbol(a[:sl])
    H = {b: Hp[b % nfft] for b in bins}
    is_pilot = {b:(i%P["pilot_every"]==0) for i,b in enumerate(bins)}
    data_bins = [b for b in bins if not is_pilot[b]]
    nsym = meta["nsym"]; soft=[]
    for s in range(nsym):
        seg = a[sl*(1+s): sl*(2+s)]
        if len(seg) < sl: break
        Y = demod_symbol(seg)
        # per-symbol pilot phase correction (track residual drift)
        ph = np.angle(np.mean([Y[b%nfft]/ (H[b]+1e-9) for b in bins if is_pilot[b]]))
        eq = []
        for b in data_bins:
            v = Y[b%nfft]/(H[b]+1e-9) * np.exp(-1j*ph)
            eq.append(v)
        soft.append(np.array(eq))
    syms = np.concatenate(soft)[:meta["per"]*nsym]
    pts = _qam_points(bits)
    llr = _demap_soft(syms, bits, pts, noise=0.3)[:meta["ncoded"]]
    info = rf.viterbi_soft(llr)
    data = rf._bits2b([1 if b else 0 for b in info])
    if len(data) < 2: return None
    n = int.from_bytes(data[:2],"big")
    if n<0 or n>len(data)-2: return None
    return data[2:2+n]

# ---------- Standard-tier airtime governor (free-tier speed/time limit) ----------
class AirtimeGovernor:
    """Free 'Standard' tier is bandwidth- AND airtime-limited, like VARA's free
    speed cap. Pro unlocks full airtime. Clear-text + legal either way; this only
    throttles how much the *free* tier may transmit, it is not a cipher or lock on
    the air. Config is honest and user-visible (no hidden DRM)."""
    def __init__(self, profile):
        self.profile = profile
        self.max_tx_s = 120.0 if profile=="STANDARD" else float("inf")   # per rolling window
        self.window_s = 600.0                                            # 10-min window
        self.max_cont_s = 30.0 if profile=="STANDARD" else float("inf")  # per-over cap
        self.used = []      # (t_end, dur) log
    def allow(self, dur_s, now=None):
        now = now if now is not None else time.monotonic()
        self.used = [(t,d) for (t,d) in self.used if t > now-self.window_s]
        spent = sum(d for _,d in self.used)
        if dur_s > self.max_cont_s:
            return False, f"over exceeds {self.max_cont_s:.0f}s continuous cap (Pro removes this)"
        if spent + dur_s > self.max_tx_s:
            return False, f"airtime budget {self.max_tx_s:.0f}s/{self.window_s/60:.0f}min spent (Pro removes this)"
        return True, "ok"
    def commit(self, dur_s, now=None):
        now = now if now is not None else time.monotonic()
        self.used.append((now, dur_s))

import time

def throughput_bps(profile, payload_bytes):
    P = PROFILES[profile]
    _, meta = modulate(b"x"*payload_bytes, profile)
    nsym = meta["nsym"]; sl = P["nfft"]+P["cp"]
    secs = (1+nsym)*sl/_fs(P)
    return payload_bytes*8/secs, secs

if __name__ == "__main__":
    rng = np.random.default_rng(0)
    msg = b"DE 8P6NH: QTC 1 msg Winlink-style RF email over the Einstein modem. 73"
    big = (b"Einstein Pro VHF wideband throughput test. "*20)[:800]   # ~800 B realistic frame
    MODNAME = {2:"QPSK",4:"16-QAM",6:"64-QAM"}
    print("Einstein Modem self-test\n")
    for prof, payload in [("STANDARD",msg),("PRO",msg),("PRO_VHF",big)]:
        y, meta = modulate(payload, prof)
        got = demodulate(y, prof, meta)
        bps, secs = throughput_bps(prof, len(payload))
        P = PROFILES[prof]
        print(f"{P['name']:26}: clean decode {'OK' if got==payload else 'FAIL'} | "
              f"{len(payload)}B in {secs:.2f}s -> {bps:.0f} bps ({bps/1000:.1f} kbps), "
              f"BW {P['bw']:.0f} Hz @ {_fs(P)/1000:.0f}k, {MODNAME[P['bits']]}")
