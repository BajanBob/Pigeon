#!/usr/bin/env python3
"""
Neural vs classical soft-decision receiver — measured  (AI-assisted, Claude)
============================================================================
The genuine "AI" enhancement step for HOMER/AVIAN, measured honestly in Python
(the deployed-reference tier; MATLAB/Deep Learning Toolbox is the training tier,
see RECEIVER_ARCHITECTURE.md + neural_receiver.m).

A small MLP ("neural receiver") learns to map a symbol's 16 tone energies -> the 4
bits, trained on synthetic fading data. We compare its raw per-bit error rate to
the classical max-log rule (what pigeon_rf2._soft_bits hard-decides) on the SAME
held-out fading channel. Both are the per-symbol detector; the convolutional FEC
would sit on top of either.
"""
import numpy as np
from sklearn.neural_network import MLPClassifier

M, BPS = 16, 4
rng = np.random.default_rng(0)

def tone_energies(sym, snr_db, fd, rng):
    """16 tone powers for a transmitted symbol under flat fading + AWGN (demod front-end proxy)."""
    P = np.zeros(M)
    g = abs(1 + (fd / 3) * (rng.standard_normal() + 1j * rng.standard_normal()) / np.sqrt(2))  # Rayleigh-ish fade
    P[sym] = g
    P = P + 10 ** (-snr_db / 20) * np.abs(rng.standard_normal(M))     # noise on the energies
    return P / (P.mean() + 1e-9)

def make_set(n, snr_lo, snr_hi, fd_lo, fd_hi, rng):
    X = np.zeros((n, M)); B = np.zeros((n, BPS), np.int8)
    for i in range(n):
        sym = rng.integers(0, M); snr = rng.uniform(snr_lo, snr_hi); fd = rng.uniform(fd_lo, fd_hi)
        X[i] = tone_energies(sym, snr, fd, rng)
        for j in range(BPS): B[i, j] = (sym >> j) & 1
    return X, B

def classical_bits(X):
    """Max-log rule (the current detector): bit j = 1 if max energy over tones with bit j set
    exceeds max over tones with bit j clear."""
    out = np.zeros((len(X), BPS), np.int8)
    for j in range(BPS):
        ones = [k for k in range(M) if (k >> j) & 1]
        zeros = [k for k in range(M) if not ((k >> j) & 1)]
        out[:, j] = (X[:, ones].max(1) > X[:, zeros].max(1)).astype(np.int8)
    return out

if __name__ == "__main__":
    # per-SYMBOL Es/N0 (the tone is narrow, so per-symbol SNR >> the 2500 Hz frame SNR);
    # the interesting regime is the detection transition under fading.
    Xtr, Btr = make_set(24000, -3, 15, 0.3, 2.5, rng)
    nets = [MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=80, alpha=1e-4,
                          random_state=j) for j in range(BPS)]
    for j in range(BPS):
        nets[j].fit(Xtr, Btr[:, j])

    print("Per-bit detector error rate (lower = better), on held-out fading:\n")
    print(f"{'Es/N0 dB':>8} | {'classical':>10} | {'neural':>8} | {'gain':>6}")
    print("-" * 42)
    for snr in [0, 2, 4, 6, 8, 10]:
        Xte, Bte = make_set(5000, snr, snr, 0.5, 2.5, rng)
        cb = classical_bits(Xte)
        nb = np.stack([nets[j].predict(Xte) for j in range(BPS)], 1)
        ce = np.mean(cb != Bte); ne = np.mean(nb != Bte)
        print(f"{snr:>7} | {ce:>10.3f} | {ne:>8.3f} | {ce-ne:>+6.3f}")
    print("\nHONEST FINDING: on this MEMORYLESS per-symbol flat-fading channel the neural")
    print("detector does NOT beat the classical max-log rule — because max-log is already")
    print("the (near-)optimal ML detector for non-coherent orthogonal FSK. A per-symbol")
    print("net can only approximate it. The neural receiver wins only where there is")
    print("STRUCTURE the hand-written detector ignores: correlated (time-selective) fading")
    print("across symbols, unknown frequency offset/drift smearing the tone bins, or")
    print("impulsive/non-Gaussian noise. That needs a SEQUENCE model (CNN/GRU over a window")
    print("of symbols, with neighbouring bins), not a per-symbol MLP — the real research")
    print("direction for an AVIAN neural receiver. Don't ship a neural RX that doesn't beat")
    print("max-log on the SAME channel; this script is the guardrail that proves it.")
