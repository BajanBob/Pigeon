# Einstein — open ultrasonic voice/data carrier (COMMERCIAL / EmComm).
# A higher-rate near-ultrasound (18-22 kHz) acoustic carrier that operates
# openly: a normal short-range sound link, for carrying low-bitrate encoded
# voice frames or data between two devices (e.g. across a command post) without
# using RF. It is NOT a secure channel by itself; wrap payloads with Beryl AES
# for confidentiality. Acoustic, ~metres range, needs ~20 kHz-capable hardware.
"""
Higher-rate than the data-only link: 4-FSK (2 bits/symbol), default 200 baud ->
~400 bit/s, enough for a low-bitrate vocoder (e.g. Codec2 1200/700) frame
stream. The modem here handles framing/modulation; a vocoder supplies the voice
bytes (Codec2 via pycodec2 if installed) — otherwise it carries arbitrary data.

    modulate(payload, fs=48000) -> float32 audio (4-FSK near-ultrasound)
    demodulate(audio, fs=48000) -> payload bytes (or None)
    encode_voice(pcm, rate)     -> bytes   (needs pycodec2; else raises)
    decode_voice(frames)        -> pcm     (needs pycodec2)
"""

import sys

try:
    import numpy as np
except ImportError:
    np = None

# four tones across 18-22 kHz (2 bits/symbol), plus a sync tone
TONES = [18200.0, 19000.0, 19800.0, 20600.0]
FSYNC = 21400.0
BAUD = 200.0
PREAMBLE_SYMS = 10


def _need_numpy():
    if np is None:
        raise RuntimeError("einstein_ultravoice needs numpy")


def _crc8(data):
    crc = 0
    for b in bytes(data):
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def _tone(freq, nsamp, fs, phase0=0.0):
    t = np.arange(nsamp) / fs
    return np.sin(2 * np.pi * freq * t + phase0), (2 * np.pi * freq * nsamp / fs + phase0) % (2 * np.pi)


def modulate(payload, fs=48000.0, baud=BAUD, level=0.5):
    """Bytes -> 4-FSK near-ultrasound audio (sync preamble, length, CRC)."""
    _need_numpy()
    payload = bytes(payload)
    frame = bytes([len(payload) & 0xFF]) + payload + bytes([_crc8(payload)])
    bits = np.unpackbits(np.frombuffer(frame, dtype=np.uint8))
    if len(bits) % 2:
        bits = np.append(bits, 0)
    syms = (bits[0::2] << 1 | bits[1::2])          # 2 bits -> tone index 0..3
    spb = int(round(fs / baud))
    out, phase = [], 0.0
    for _ in range(PREAMBLE_SYMS):
        seg, phase = _tone(FSYNC, spb, fs, phase)
        out.append(seg)
    for s in syms:
        seg, phase = _tone(TONES[int(s)], spb, fs, phase)
        out.append(seg)
    audio = level * np.concatenate(out)
    f = int(fs * 0.003)
    if f and len(audio) > 2 * f:
        r = np.linspace(0, 1, f); audio[:f] *= r; audio[-f:] *= r[::-1]
    return audio.astype(np.float32)


def _power(x, freq, fs):
    n = len(x)
    k = 2 * np.pi * freq / fs
    c = 2 * np.cos(k)
    s1 = s2 = 0.0
    for v in x:
        s0 = v + c * s1 - s2
        s2 = s1; s1 = s0
    return s1 * s1 + s2 * s2 - c * s1 * s2


def demodulate(audio, fs=48000.0, baud=BAUD):
    """4-FSK near-ultrasound audio -> payload bytes (aligns on sync preamble)."""
    _need_numpy()
    x = np.asarray(audio, dtype=np.float64)
    spb = int(round(fs / baud))
    hop = spb // 4
    start = None
    for i in range(0, max(1, len(x) - spb), hop):
        w = x[i:i + spb]
        ps = _power(w, FSYNC, fs)
        if ps > 5 * (sum(_power(w, f, fs) for f in TONES) + 1e-12):
            start = i
            break
    if start is None:
        return None
    i = start + PREAMBLE_SYMS * spb
    syms = []
    while i + spb <= len(x):
        w = x[i:i + spb]
        pw = [_power(w, f, fs) for f in TONES]
        if max(pw) < 1e-9:
            break
        syms.append(int(np.argmax(pw)))
        i += spb
    bits = []
    for s in syms:
        bits.append((s >> 1) & 1); bits.append(s & 1)
    if len(bits) < 16:
        return None
    by = np.packbits(np.array(bits[:len(bits) - (len(bits) % 8)], dtype=np.uint8)).tobytes()
    n = by[0]
    if len(by) < n + 2:
        return None
    payload, crc = by[1:1 + n], by[1 + n]
    return payload if _crc8(payload) == crc else None


# --- optional voice vocoder (Codec2) -----------------------------------------

def encode_voice(pcm, rate=1200):
    try:
        import pycodec2
    except Exception as e:
        raise RuntimeError("voice needs pycodec2 (pip install pycodec2) + Codec2") from e
    c2 = pycodec2.Codec2(rate)
    return c2.encode(np.asarray(pcm, dtype=np.int16))


def decode_voice(frames, rate=1200):
    import pycodec2
    return pycodec2.Codec2(rate).decode(frames)


def _selftest():
    _need_numpy()
    print("Einstein ultrasonic open voice/data carrier self-test (4-FSK)")
    print("-" * 60)
    ok_all = True
    for msg in (b"VOICEFRAME:0001", b"PTT=1 unit=charlie", bytes(range(24))):
        aud = modulate(msg, fs=48000)
        rx = aud + 0.01 * np.random.randn(len(aud))
        out = demodulate(rx, fs=48000)
        ok = out == msg
        ok_all &= ok
        print(f"  {'OK ' if ok else 'FAIL'}  {len(aud)/48000:5.2f}s  "
              f"{int(BAUD*2)} bit/s  -> {out!r}")
    try:
        import pycodec2  # noqa
        print("  pycodec2: available (real voice frames supported)")
    except Exception:
        print("  pycodec2: not installed (carrier works; add pycodec2 for voice)")
    print("\nNote: acoustic, ~metres range, open operation; ~20 kHz-capable "
          "hardware; wrap with Beryl AES for confidentiality.")
    return 0 if ok_all else 1


def main(argv):
    if "--selftest" in argv or not argv:
        return _selftest()
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
