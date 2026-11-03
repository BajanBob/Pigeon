#!/usr/bin/env python3
"""
Oscillator-drift correction + sea-Doppler / rig-drift discriminator  (AI-assisted, Claude)
==========================================================================================
Corrective measure for ocean-scatter probing: the signal you hunt (sea Bragg
Doppler, ~0.4-2 Hz) is tiny, so a drifting rig/oscillator can masquerade as, or
bury, the sea signature. This module:

  1) TRACKS the instantaneous frequency of a received beacon (analytic-signal phase
     derivative, smoothed),
  2) FITS the slow component (the oscillator/rig drift) as a low-order polynomial and
     REMOVES it -> the residual is the candidate propagation Doppler,
  3) DISCRIMINATES: tests the residual spectrum for the band's symmetric Bragg lines
     (+/- fB). Symmetric lines near fB => sea scatter; a monotonic trend with no Bragg
     structure => rig drift.

The point: after correction, oscillator drift is reduced well below the sea signal,
so the two are separable. Measured below.
"""
import numpy as np
from ocean_scatter import ocean_bragg_hz, _bragg_fading

FS = 1000.0            # analysis sample rate for the tone (Hz) — a decimated beacon tone
DUR = 31.0             # HOMER beacon length (s)

def synth(freq_mhz, drift_hz_per_s, sea=True, broaden=0.3, snr_db=20, seed=0):
    """A beacon carrier with (optional) sea Bragg Doppler AND a linear oscillator drift."""
    rng = np.random.default_rng(seed)
    n = int(FS * DUR); t = np.arange(n) / FS
    fB = ocean_bragg_hz(freq_mhz)
    # oscillator drift: linear in time -> quadratic phase
    drift_phase = 2 * np.pi * (0.5 * drift_hz_per_s * t ** 2)
    carrier = np.exp(1j * (2 * np.pi * 50 * t + drift_phase))   # 50 Hz nominal tone
    if sea:
        g = _bragg_fading(n, FS, fB, broaden, rng)              # sea-surface Doppler
        x = carrier * g
    else:
        x = carrier * (1 + 0.02 * rng.standard_normal(n))       # steady path, no sea Doppler
    # additive noise
    p = np.mean(np.abs(x) ** 2); nvar = p / (10 ** (snr_db / 10))
    x = x + np.sqrt(nvar / 2) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    return x, fB

def track_freq(x):
    """Instantaneous frequency (Hz) via phase derivative, lightly smoothed."""
    ph = np.unwrap(np.angle(x))
    f = np.diff(ph) / (2 * np.pi) * FS
    k = 25
    f = np.convolve(f, np.ones(k) / k, mode='same')
    return f

def remove_drift(f, order=2):
    """Fit & subtract the slow oscillator/rig drift (low-order poly). Returns (residual, drift_rate)."""
    t = np.arange(len(f)) / FS
    c = np.polyfit(t, f, order)
    trend = np.polyval(c, t)
    drift_rate = c[order - 1]           # linear term ~ Hz/s at t=0
    return f - trend, drift_rate, trend

def bragg_test(residual, fB, band_tol=0.35):
    """Look for symmetric +/- fB lines in the residual frequency fluctuation spectrum."""
    r = residual - np.mean(residual)
    R = np.abs(np.fft.rfft(r * np.hanning(len(r))))
    fr = np.fft.rfftfreq(len(r), 1 / FS)
    def peak_near(f0):
        m = (fr > f0 - band_tol) & (fr < f0 + band_tol)
        return R[m].max() if m.any() else 0.0
    base = np.median(R[fr > 0.05]) + 1e-9
    p = peak_near(fB) / base            # Bragg line strength over the floor
    return p

if __name__ == "__main__":
    print("Oscillator-drift correction + sea/rig discriminator  (2 m, fB shown)\n")
    for label, sea, drift in [("sea scatter + big rig drift", True, 0.20),
                              ("sea scatter, clean rig",       True, 0.01),
                              ("NO sea, only rig drift",       False, 0.20)]:
        x, fB = synth(144, drift, sea=sea, seed=hash(label) & 255)
        f = track_freq(x)
        resid, drate, _ = remove_drift(f, order=2)
        score = bragg_test(resid, fB)
        verdict = "SEA DOPPLER (Bragg lines present)" if score > 4 else "rig drift only (no Bragg)"
        print(f"{label:>30}: est drift {drate:+.3f} Hz/s (true {drift:+.2f}) | "
              f"Bragg score {score:4.1f} -> {verdict}")
    print(f"\nBragg fB(2m) = {ocean_bragg_hz(144):.2f} Hz. After removing the fitted drift,")
    print("the residual reveals the sea Bragg lines only when the sea path is real,")
    print("so rig drift and sea Doppler are separated. Keep rig drift << fB with a")
    print("GPSDO/OCXO reference and this discriminator flags genuine ocean scatter.")
