#!/usr/bin/env python3
"""
Ocean Scatter — experimental weak-signal propagation model & HOMER test
=======================================================================
R&D, NOT an established mode. "Ocean Scatter Propagation/Mode (OSP/OSM)" is a
Pigeon-line idea: use signals scattered off the moving sea surface for over-the-
horizon paths over water. The sea surface imposes a characteristic DOPPLER
signature (the Bragg lines well known from HF ocean radar / CODAR), broadened by
sea state. This script:

  1) computes the first-order ocean Bragg Doppler for a band (physics, not hand-wave),
  2) builds an ocean-scatter channel (two Bragg lines +/- fB, Gaussian-broadened
     by sea state) and applies it to the HOMER (AVIAN) waveform,
  3) measures HOMER's decode threshold on it, and shows what a dedicated
     Ocean-Scatter waveform would need to change.

Physics: EM wavelength L = c/f. First-order Bragg resonance is with the ocean
wave of length L/2, whose deep-water gravity-wave phase speed is
    v = sqrt(g * (L/2) / (2*pi)).
The scattered Doppler shift is fB = 2*v / L  (two signs: advancing/receding waves).
"""
import numpy as np
import pigeon_rf2 as rf

G = 9.81; C = 299792458.0

def ocean_bragg_hz(freq_mhz):
    L = C / (freq_mhz * 1e6)                 # EM wavelength (m)
    lam_ocean = L / 2.0                        # resonant ocean wavelength
    v = np.sqrt(G * lam_ocean / (2 * np.pi))   # deep-water gravity-wave phase speed
    return 2 * v / L                           # Bragg Doppler (Hz)

def ocean_channel(sig, fs, fB, broaden_hz, rng):
    """Ocean-scatter channel: fading with a two-Bragg-line Doppler PSD."""
    n = len(sig)
    analytic = _hilbert(sig)
    g = _bragg_fading(n, fs, fB, broaden_hz, rng)
    return np.real(g * analytic)

def _bragg_fading(n, fs, fB, broaden, rng):
    w = rng.normal(size=n) + 1j * rng.normal(size=n)
    f = np.fft.fftfreq(n, 1 / fs)
    # two Gaussian-broadened Bragg lines at +/- fB
    psd = np.exp(-0.5 * ((f - fB) / (broaden + 1e-9)) ** 2) + \
          np.exp(-0.5 * ((f + fB) / (broaden + 1e-9)) ** 2)
    g = np.fft.ifft(np.fft.fft(w) * np.sqrt(psd))
    g /= (np.sqrt(np.mean(np.abs(g) ** 2)) + 1e-12)
    return g

def _hilbert(x):
    X = np.fft.fft(x); n = len(x); h = np.zeros(n)
    if n % 2 == 0: h[0] = h[n // 2] = 1; h[1:n // 2] = 2
    else: h[0] = 1; h[1:(n + 1) // 2] = 2
    return np.fft.ifft(X * h)

def measure(label, freq_mhz, sea_state_broaden, snrs, trials=12, seed=0):
    fB = ocean_bragg_hz(freq_mhz)
    print(f"\n=== {label}: {freq_mhz} MHz, Bragg fB = {fB:.2f} Hz, broadening {sea_state_broaden} Hz ===")
    rng = np.random.default_rng(seed)
    for snr in snrs:
        ok = 0
        for _ in range(trials):
            sig = rf.modulate("8P6NH", "GK03")
            sig = ocean_channel(sig, rf.FS, fB, sea_state_broaden, rng)
            rx = rf.add_noise_snr2500(sig, snr, rng)
            r = rf.demodulate(rx)
            ok += (r is not None and r["callsign"] == "8P6NH")
        print(f"  SNR {snr:>4} dB/2500Hz : {ok:2d}/{trials}  ({100*ok/trials:.0f}%)")

if __name__ == "__main__":
    print("Ocean Bragg Doppler by band (first-order, deep water):")
    for fmhz in [14, 50, 144, 222, 432]:
        print(f"  {fmhz:>4} MHz -> fB = {ocean_bragg_hz(fmhz):5.2f} Hz")
    # HF: narrow Bragg, calm-ish sea
    measure("HF ocean scatter (calm)", 14, 0.1, [-16, -18, -20, -21])
    # 2 m: wider Bragg + moderate sea-state broadening
    measure("2 m ocean scatter (moderate sea)", 144, 0.8, [-10, -12, -14, -16])
    print("\nNote: HOMER's ~59 Hz tones tolerate HF Bragg (sub-Hz) well; at VHF the")
    print("broadened Doppler argues for a dedicated OSM waveform with wider tone")
    print("spacing and per-symbol Doppler/Bragg tracking. This is the R&D next step.")
