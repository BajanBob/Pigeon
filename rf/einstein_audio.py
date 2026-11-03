# Einstein — standalone soundcard audio engine.
# Gives Einstein a real rig-audio pipe on a PC/Pi without the browser:
# capture the rig's receive audio (USB codec / line-in) for the analyzer,
# SSP, drift and ocean-scatter tools, and play modem/beacon audio to TX.
#
# This is ADDITIVE to the in-app WebAudio / getUserMedia path (which keeps
# working in the browser build). On the desktop this module lets the Python
# tools run the station on their own.
#
# Uses sounddevice (PortAudio) + numpy. Both are optional at import time so
# the module loads for device listing / help even where PortAudio is absent.
"""
    list_devices()                      -> ([{index,name,inputs,outputs}], err)
    capture(seconds, device, rate)      -> float32 mono numpy array
    play(signal, device, rate)          -> None (blocks until done)
    analyze(audio, rate)                -> {peak_hz, snr_db, rms, spectrum...}
    AudioPipe(radio_id).capture(sec)    -> audio, using a radio preset's device/rate

CLI:
    python3 einstein_audio.py --devices
    python3 einstein_audio.py --analyze 3 [--in <dev>] [--rate 48000]
    python3 einstein_audio.py --selftest       # no hardware; synthetic tone
"""

import sys

try:
    import numpy as np
except ImportError:
    np = None


def _need_numpy():
    if np is None:
        raise RuntimeError("einstein_audio needs numpy (pip install numpy)")


# --------------------------------------------------------------------------
# Device discovery
# --------------------------------------------------------------------------

def list_devices():
    """Every audio device PortAudio sees (feed the rig's audio into one)."""
    try:
        import sounddevice as sd
        devs = []
        for i, d in enumerate(sd.query_devices()):
            devs.append({"index": i, "name": d["name"],
                         "inputs": d["max_input_channels"],
                         "outputs": d["max_output_channels"]})
        return devs, ""
    except Exception as e:
        return [], f"sounddevice unavailable: {e}"


def _resolve_device(name_or_index):
    """Accept a device index (int/str digits) or a name substring."""
    if name_or_index in (None, ""):
        return None
    s = str(name_or_index)
    if s.lstrip("-").isdigit():
        return int(s)
    devs, _ = list_devices()
    for d in devs:
        if s.lower() in d["name"].lower():
            return d["index"]
    return name_or_index  # let sounddevice try to match


# --------------------------------------------------------------------------
# Capture / playback
# --------------------------------------------------------------------------

def capture(seconds=3.0, device=None, rate=48000):
    """Record mono float32 audio from the rig's receive device."""
    _need_numpy()
    import sounddevice as sd
    dev = _resolve_device(device)
    n = int(seconds * rate)
    audio = sd.rec(n, samplerate=rate, channels=1, dtype="float32", device=dev)
    sd.wait()
    return audio.reshape(-1)


def play(signal, device=None, rate=48000):
    """Play float32 mono audio to the TX device (blocks until finished)."""
    _need_numpy()
    import sounddevice as sd
    dev = _resolve_device(device)
    sig = np.asarray(signal, dtype="float32").reshape(-1)
    sd.play(sig, samplerate=rate, device=dev)
    sd.wait()


def stream_blocks(device=None, rate=48000, block=4096):
    """Yield successive float32 blocks for a live analyzer / decoder.
    Stop by closing the generator (GeneratorExit)."""
    _need_numpy()
    import sounddevice as sd
    dev = _resolve_device(device)
    with sd.InputStream(samplerate=rate, channels=1, dtype="float32",
                        blocksize=block, device=dev) as st:
        while True:
            data, _ = st.read(block)
            yield data.reshape(-1)


# --------------------------------------------------------------------------
# Analysis — the audio pipe for SSP / drift / ocean-scatter / analyzer
# --------------------------------------------------------------------------

def analyze(audio, rate=48000, passband=(300.0, 2700.0)):
    """Spectrum + peak tone + estimated SNR of captured SSB passband audio.
    This is the same measurement the in-app analyzer makes, available to the
    Python tools so SSP/drift can run on real rig audio off a soundcard."""
    _need_numpy()
    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    if len(x) < 256:
        return {"error": "too few samples"}
    x = x - x.mean()
    rms = float(np.sqrt(np.mean(x * x)))
    # Welch-ish averaged periodogram
    nfft = 4096
    win = np.hanning(nfft)
    step = nfft // 2
    acc = np.zeros(nfft // 2 + 1)
    cnt = 0
    for i in range(0, len(x) - nfft, step):
        seg = x[i:i + nfft] * win
        acc += np.abs(np.fft.rfft(seg)) ** 2
        cnt += 1
    if cnt == 0:
        seg = np.zeros(nfft); seg[:len(x)] = x[:nfft]
        acc = np.abs(np.fft.rfft(seg * win)) ** 2
        cnt = 1
    psd = acc / cnt
    freqs = np.fft.rfftfreq(nfft, 1.0 / rate)
    band = (freqs >= passband[0]) & (freqs <= passband[1])
    if not band.any():
        band = freqs > 0
    bpsd = psd[band]; bfreq = freqs[band]
    pk = int(np.argmax(bpsd))
    peak_hz = float(bfreq[pk])
    peak_pow = float(bpsd[pk])
    # noise floor = median of in-band bins excluding a window around the peak
    mask = np.ones(len(bpsd), dtype=bool)
    guard = max(1, int(50 / (freqs[1] - freqs[0])))
    mask[max(0, pk - guard):pk + guard] = False
    noise = float(np.median(bpsd[mask])) if mask.any() else float(np.median(bpsd))
    snr_db = 10.0 * np.log10(peak_pow / noise) if noise > 0 else float("inf")
    # coarse spectrum for a mini waterfall (64 bins across the passband)
    nb = 64
    idx = np.linspace(0, len(bpsd) - 1, nb).astype(int)
    spec = (10 * np.log10(bpsd[idx] + 1e-12)).tolist()
    return {"peak_hz": round(peak_hz, 1),
            "snr_db": round(snr_db, 1),
            "rms": round(rms, 5),
            "noise_floor_db": round(10 * np.log10(noise + 1e-12), 1),
            "n_samples": len(x),
            "spectrum_db": [round(v, 1) for v in spec],
            "passband": passband}


def measured_offset_hz(audio, rate, expected_hz):
    """Fine frequency of the dominant tone near expected_hz — feeds the
    drift / sea-Bragg-Doppler discriminator (rf/drift_discriminator.py)."""
    _need_numpy()
    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    x = (x - x.mean()) * np.hanning(len(x))
    nfft = 1 << (len(x) - 1).bit_length()
    nfft = max(nfft, 1 << 16)
    sp = np.abs(np.fft.rfft(x, nfft))
    freqs = np.fft.rfftfreq(nfft, 1.0 / rate)
    lo, hi = expected_hz - 200, expected_hz + 200
    b = (freqs >= lo) & (freqs <= hi)
    if not b.any():
        return None
    k = np.argmax(np.where(b, sp, 0))
    # parabolic interpolation for sub-bin accuracy
    if 1 <= k < len(sp) - 1:
        a0, a1, a2 = sp[k - 1], sp[k], sp[k + 1]
        d = (a0 - a2) / (2 * (a0 - 2 * a1 + a2) + 1e-20)
    else:
        d = 0.0
    f = (k + d) * rate / nfft
    return {"freq_hz": round(float(f), 3), "offset_hz": round(float(f - expected_hz), 3)}


# --------------------------------------------------------------------------
# AudioPipe — tie capture/playback to a chosen radio preset
# --------------------------------------------------------------------------

class AudioPipe:
    """Captures/plays using a radio preset's expected device + sample rate,
    so the analyzer and SSP get the rig's audio with one call."""

    def __init__(self, radio_id=None, in_dev=None, out_dev=None, rate=None):
        self.in_dev, self.out_dev = in_dev, out_dev
        self.rate = rate or 48000
        self.radio = None
        if radio_id:
            try:
                import einstein_radios as R
                self.radio = R.get(radio_id)
                self.rate = rate or self.radio.get("sample_rate", 48000)
                if in_dev is None:
                    self.in_dev = self.radio.get("audio")
                if out_dev is None:
                    self.out_dev = self.radio.get("audio")
            except Exception:
                pass

    def capture(self, seconds=3.0):
        return capture(seconds, device=self.in_dev, rate=self.rate)

    def play(self, signal):
        return play(signal, device=self.out_dev, rate=self.rate)

    def analyze(self, seconds=3.0):
        return analyze(self.capture(seconds), rate=self.rate)


# --------------------------------------------------------------------------
# CLI / self-test
# --------------------------------------------------------------------------

def _selftest():
    """No hardware: synthesize a 1500 Hz tone in noise and analyze it."""
    _need_numpy()
    rate = 48000
    t = np.arange(int(2 * rate)) / rate
    sig = 0.3 * np.sin(2 * np.pi * 1500 * t) + 0.02 * np.random.randn(len(t))
    r = analyze(sig, rate)
    off = measured_offset_hz(sig, rate, 1500.0)
    print("analyze():", {k: r[k] for k in ("peak_hz", "snr_db", "noise_floor_db", "rms")})
    print("measured_offset_hz(1500):", off)
    ok = abs(r["peak_hz"] - 1500) < 15 and r["snr_db"] > 10 and abs(off["offset_hz"]) < 2
    print("einstein_audio self-test", "OK" if ok else "FAILED")
    return 0 if ok else 1


def main(argv):
    if "--devices" in argv:
        devs, err = list_devices()
        if err:
            print(err); return 1
        for d in devs:
            print(f"  [{d['index']:2d}] in={d['inputs']} out={d['outputs']}  {d['name']}")
        return 0
    if "--selftest" in argv:
        return _selftest()
    if "--analyze" in argv:
        i = argv.index("--analyze")
        secs = float(argv[i + 1]) if i + 1 < len(argv) else 3.0
        dev = argv[argv.index("--in") + 1] if "--in" in argv else None
        rate = int(argv[argv.index("--rate") + 1]) if "--rate" in argv else 48000
        print(f"capturing {secs}s from {dev or 'default'} @ {rate} Hz…")
        a = capture(secs, device=dev, rate=rate)
        import json
        print(json.dumps(analyze(a, rate), indent=2))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    raise SystemExit(main(sys.argv[1:]))
