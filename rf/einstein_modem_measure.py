#!/usr/bin/env python3
"""Measure Einstein modem FER vs Eb/N0 under AWGN and Watterson HF fading.
Honest numbers for MODEM.md — AI-assisted (Claude)."""
import numpy as np, einstein_modem as em

def awgn(sig, snr_db):
    p = np.mean(sig**2)
    n = np.sqrt(p/(10**(snr_db/10))/2) * np.random.randn(len(sig))
    return sig + n

def watterson(sig, fs=em.FS, spread_hz=1.0, delay_ms=2.0):
    # 2-path, Rayleigh-faded, Doppler-spread (CCIR 520 'moderate' ~1 Hz / 2 ms)
    d = int(delay_ms*1e-3*fs)
    out = np.zeros(len(sig)+d)
    for path, g in [(0,1.0),(d,0.8)]:
        # independent Gaussian fading process, low-pass to spread_hz
        n = (np.random.randn(len(sig))+1j*np.random.randn(len(sig)))
        F = np.fft.fft(n); f = np.fft.fftfreq(len(sig), 1/fs)
        F *= np.exp(-(f/spread_hz)**2); fade = np.fft.ifft(F)
        fade = fade/ (np.std(fade)+1e-9)
        seg = sig*np.real(fade)*g
        out[path:path+len(sig)] += seg
    return out[:len(sig)]

def run(profile, snrs, trials=60, chan="awgn"):
    msg = b"DE 8P6NH QTC Einstein RF email test frame payload 64 bytes...."[:64]
    fer=[]
    for snr in snrs:
        fail=0
        for _ in range(trials):
            y,meta = em.modulate(msg, profile)
            if chan=="awgn": r = awgn(y,snr)
            else:           r = awgn(watterson(y), snr)
            got = em.demodulate(r, profile, meta)
            if got!=msg: fail+=1
        fer.append(fail/trials)
    return fer

if __name__=="__main__":
    np.random.seed(1)
    print("Einstein Modem — FER vs SNR (per-sample audio SNR, dB)\n")
    for prof in ["STANDARD","PRO"]:
        snrs=list(range(-2,16,2))
        a=run(prof,snrs,50,"awgn")
        w=run(prof,snrs,50,"fading")
        print(f"[{em.PROFILES[prof]['name']}]")
        print("  SNR dB :", "  ".join(f"{s:4d}" for s in snrs))
        print("  AWGN FER:", " ".join(f"{x:4.2f}" for x in a))
        print("  Fade FER:", " ".join(f"{x:4.2f}" for x in w))
        # find ~10% FER threshold
        def thr(fe):
            for s,f in zip(snrs,fe):
                if f<=0.1: return s
            return None
        print(f"  ~10% FER: AWGN {thr(a)} dB,  fading {thr(w)} dB\n")
