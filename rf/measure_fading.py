#!/usr/bin/env python3
"""
PigeonFSK-2 — honest threshold measurement under AWGN and HF (Watterson) fading.
Reuses the SHIPPING codec in pigeon_rf2.py (same modulate/demodulate), so these
numbers reflect the real deployed decoder, not a toy.

Watterson HF model: N independent Rayleigh paths, each a complex-Gaussian gain
process with a Gaussian Doppler spectrum (spread fd), plus a path delay. This is
the standard ITU-R HF ionospheric model (iturHFxx in MATLAB's stdchan).

SNR is in the 2500 Hz reference bandwidth (FT8 convention).
"""
import numpy as np, time
import pigeon_rf2 as rf

def watterson(sig, fs, delays_ms, doppler_hz, rng):
    """Apply a multipath Rayleigh-fading HF channel to a real passband signal."""
    n = len(sig)
    analytic = _hilbert(sig)
    out = np.zeros(n, complex)
    npaths = len(delays_ms)
    for p in range(npaths):
        d = int(round(delays_ms[p] * 1e-3 * fs))
        g = _fading_process(n, fs, doppler_hz, rng) / np.sqrt(npaths)
        delayed = np.zeros(n, complex)
        if d < n:
            delayed[d:] = analytic[:n - d]
        out += g * delayed
    return np.real(out)

def _hilbert(x):
    X = np.fft.fft(x); n = len(x); h = np.zeros(n)
    if n % 2 == 0:
        h[0] = h[n // 2] = 1; h[1:n // 2] = 2
    else:
        h[0] = 1; h[1:(n + 1) // 2] = 2
    return np.fft.ifft(X * h)

def _fading_process(n, fs, fd, rng):
    """Unit-power complex Gaussian process with a Gaussian Doppler PSD of spread fd."""
    w = rng.normal(size=n) + 1j * rng.normal(size=n)
    f = np.fft.fftfreq(n, 1 / fs)
    psd = np.exp(-0.5 * (f / (fd + 1e-9)) ** 2)          # Gaussian Doppler shape
    H = np.sqrt(psd)
    g = np.fft.ifft(np.fft.fft(w) * H)
    g /= (np.sqrt(np.mean(np.abs(g) ** 2)) + 1e-12)       # normalize to unit power
    return g

def sweep(label, snrs, trials, channel=None, seed=0):
    print(f"\n=== {label} ===")
    rng = np.random.default_rng(seed)
    results = {}
    for snr in snrs:
        ok = 0
        for _ in range(trials):
            sig = rf.modulate("8P6NH", "GK03")           # Barbados grid
            if channel is not None:
                sig = channel(sig, rng)
            rx = rf.add_noise_snr2500(sig, snr, rng)
            r = rf.demodulate(rx)
            ok += (r is not None and r["callsign"] == "8P6NH" and r["grid"] == "GK03")
        results[snr] = ok / trials
        print(f"  SNR {snr:>4} dB/2500Hz : {ok:2d}/{trials}  ({100*ok/trials:.0f}%)")
    return results

def false_alarm(trials, seed=99):
    rng = np.random.default_rng(seed)
    n = len(rf.modulate("8P6NH", "GK03"))
    fa = 0
    for _ in range(trials):
        r = rf.demodulate(rng.normal(0, 1, n))
        fa += (r is not None)
    print(f"\nFalse decodes from pure noise: {fa}/{trials}")
    return fa

if __name__ == "__main__":
    t0 = time.time()
    # 1) AWGN baseline — should reproduce the ~-21 dB threshold claim
    sweep("AWGN (baseline)", [-18, -19, -20, -21, -22], trials=15, seed=1)

    # 2) HF fading — ITU-R "moderate": 2 paths ~1 ms, 0.5 Hz Doppler
    moderate = lambda s, rng: watterson(s, rf.FS, [0.0, 1.0], 0.5, rng)
    sweep("HF fading — moderate (2 path, 1 ms, 0.5 Hz)", [-12, -14, -16, -18, -20], trials=15, channel=moderate, seed=2)

    # 3) HF fading — "poor": 2 paths ~2 ms, 1.0 Hz Doppler
    poor = lambda s, rng: watterson(s, rf.FS, [0.0, 2.0], 1.0, rng)
    sweep("HF fading — poor (2 path, 2 ms, 1.0 Hz)", [-10, -12, -14, -16, -18], trials=15, channel=poor, seed=3)

    false_alarm(30)
    print(f"\n[done in {time.time()-t0:.0f}s]")
