# MATLAB-enhanced receiver — recommended computing architecture

How to use MATLAB to push the HOMER/AVIAN (and OSM ocean-scatter) **receiver**
further — a neural/soft-decision weak-signal decoder — and then run it for real on
a station. AI-assisted (Claude). The guiding principle is the split we've already
used: **MATLAB for research & validation, a lean exported decoder for deployment.**
They cross-check each other.

```
            ┌────────────────────────── RESEARCH TIER (offline, GPU) ──────────────────────────┐
  SDR IQ ──▶│  MATLAB                                                                           │
  captures  │   • Communications Toolbox — waveform, LDPC/Viterbi, Watterson/Rician channels    │
  (.mat/    │   • DSP System Toolbox — filters, multirate, spectral/Doppler analysis            │
  SigMF)    │   • Deep Learning Toolbox — NEURAL RECEIVER (CNN/GRU) trained on GPU (gpuArray)    │
  +         │   • Parallel Computing Toolbox — multi-GPU / cluster BER-vs-SNR-vs-seastate sweeps │
  synthetic │   • (optional) MATLAB Parallel Server for large sweeps on a cluster               │
  channel   └───────────────┬──────────────────────────────────────────────────────────────────┘
                            │  export the VALIDATED receiver
          ┌─────────────────┼─────────────────────────────────────────────┐
          ▼                 ▼                 ▼                            ▼
   MATLAB Coder → C   GPU Coder → CUDA   exportONNXNetwork            codegen test vectors
   (CPU edge build)   (real-time GPU)    (→ Python onnxruntime)       (bit-exact MATLAB↔deploy)
          │                 │                 │
          └─────────────────┴─────────────────┴──────▶  DEPLOYMENT TIER (real-time, station)
                                                         • runs beside WSJT-X / Einstein
                                                         • SDR front-end (Pluto/USRP/RTL-SDR)
                                                         • feeds decodes to Einstein's log
```

## Tier 1 — Research & training (where MATLAB earns its place)
**Toolboxes:** Communications, DSP System, Deep Learning, Parallel Computing;
optionally Phased Array/Antenna (beamforming), and the SDR support packages
(Communications Toolbox Support Package for ADALM-Pluto / USRP / RTL-SDR).

**What you do here**
- Generate training data two ways and mix them: (a) **synthetic** — the HOMER
  waveform through the Watterson HF and the ocean Bragg-Doppler channels
  (`ocean_scatter.py`'s model, ported to MATLAB) across SNR/sea-state/Doppler; and
  (b) **real IQ** captured off-air from your SDR over sea paths (store as `.mat` or
  SigMF). Real + synthetic is what makes a neural receiver generalize.
- Train a **neural receiver** (the genuine "AI" step): a small 1-D CNN (optionally
  a GRU head) that maps the received IQ / per-tone soft metrics to soft bits,
  learning to beat the hand-written detector under fading and Doppler. See
  `neural_receiver.m`.
- Validate rigorously: BER-vs-Eb/N0 curves (BERTool), AWGN vs Watterson vs ocean
  scatter, neural vs classical soft-Viterbi, with confidence intervals from many
  Parallel-Computing runs.

**Hardware:** a workstation (or cloud instance) with **one NVIDIA GPU**
(RTX 4070/4090 or A4000/A6000-class, ≥12 GB VRAM) and ≥32 GB RAM is plenty to start;
scale to multi-GPU / a cluster only for big sweeps. Cloud options: MathWorks Cloud
Center on AWS/Azure, or a rented GPU instance. CPU-only works but training is slow.

## Tier 2 — Export (MATLAB → deployable)
Pick by where the decoder runs:
- **MATLAB Coder → C/C++** for a portable CPU decoder (Windows/Linux/embedded/SDR host).
- **GPU Coder → CUDA** when the neural receiver must run in real time on a GPU/Jetson.
- **`exportONNXNetwork`** → run the trained net in **Python (onnxruntime)** as the
  deployed reference decoder — this matches our existing Python-reference split and
  keeps the station software open.
- Always emit **code-generation test vectors** so the deployed decoder is **bit-exact**
  against MATLAB on the same inputs (the cross-check that keeps you honest).

## Tier 3 — Deployment (real-time, at the station)
- **Edge hardware:** the classical DSP runs fine on any modern multi-core CPU; for a
  real-time **neural** receiver, a small GPU or an **NVIDIA Jetson Orin Nano** is ideal
  and low-power for a remote coastal site.
- **Front-end:** SDR (ADALM-Pluto / USRP / RTL-SDR) → the exported decoder → decodes
  with SNR + frequency offset → **Einstein** (log + the sea-Doppler/rig-drift
  discriminator + duct prediction) and PSK Reporter.
- Discipline the clock with a **GPSDO/OCXO** so rig drift ≪ the sea Bragg Doppler
  (≈0.4–2 Hz) — the receiver can only exploit sea Doppler if the reference is stable.

## Data pipeline (one line)
`SDR capture + synthetic channels  →  MATLAB train/validate (GPU)  →  Coder/GPU Coder/ONNX  →  real-time decoder  →  Einstein`

## Honest notes
- MATLAB is the right tool for **research, FEC/ML design and validation**; the
  **deployed reference stays Python/C** (open, runs on the station). Neither replaces
  WSJT-X for the established modes — this path is for the original HOMER/OSM line.
- A neural receiver's gain is real but bounded; prove it against the classical
  soft-Viterbi on the *same* channel before shipping it, with code-gen bit-exactness.
- For most hams, **Tier-1 on one GPU + ONNX-to-Python deployment on the station PC**
  is the sweet spot — no cluster, no CUDA codegen needed to start.
