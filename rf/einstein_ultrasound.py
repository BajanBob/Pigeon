# Einstein — ultrasonic data-over-sound channel (COMMERCIAL / EmComm).
#
# A short-range, RF-FREE acoustic link in the near-ultrasound band (18–22 kHz)
# for device-to-device transfer of keys, config or short messages when you do
# not want to put anything on the air — e.g. pairing two EmComm units across a
# table, air-gapped key exchange, or a local handshake.
#
# HONEST SCOPE:
# - This is ACOUSTIC (sound), not RF. Range is a few metres line-of-ear, needs
#   a speaker/mic that reach ~20 kHz (many laptop/phone parts roll off there),
#   and ~18–19 kHz is audible to young people and many animals.
# - It is an air-gapped convenience channel, not a secure one by itself; wrap
#   the payload with Beryl's AES-256-GCM for confidentiality.
"""
    modulate(data_bytes, fs=48000) -> float32 audio (near-ultrasound BFSK)
    demodulate(audio, fs=48000)    -> data_bytes (or None if no frame found)
Framing: sync preamble (FSYNC) · length byte · payload · CRC-8. BFSK:
bit0=F0, bit1=F1, 100 baud by default, tones inside 18–22 kHz.
"""

import sys

try:
    import numpy as np
except ImportError:
    np = None

F0 = 18500.0       # bit 0
F1 = 19500.0       # bit 1
FSYNC = 20500.0    # preamble / alignment tone
BAUD = 100.0
PREAMBLE_SYMS = 8


def _need_numpy():
    if np is None:
        raise RuntimeError("einstein_ultrasound needs numpy (pip install numpy)")


def _crc8(data):
    crc = 0
    for b in bytes(data):
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def _tone(freq, nsamp, fs, phase0=0.0):
    t = np.arange(nsamp) / fs
    return np.sin(2 * np.pi * freq * t + phase0), (2 * np.pi * freq * nsamp / fs + phase0)


def modulate(data, fs=48000.0, baud=BAUD, level=0.5):
    """Bytes -> near-ultrasound BFSK audio with sync preamble, length and CRC."""
    _need_numpy()
    data = bytes(data)
    frame = bytes([len(data) & 0xFF]) + data + bytes([_crc8(data)])
    bits = np.unpackbits(np.frombuffer(frame, dtype=np.uint8))
    spb = int(round(fs / baud))
    out = []
    phase = 0.0
    for _ in range(PREAMBLE_SYMS):                 # alignment preamble
        seg, phase = _tone(FSYNC, spb, fs, phase)
        out.append(seg)
    for b in bits:                                 # payload BFSK
        seg, phase = _tone(F1 if b else F0, spb, fs, phase)
        out.append(seg)
    audio = level * np.concatenate(out)
    # short raised-cosine fade to avoid clicks
    f = int(fs * 0.003)
    if f and len(audio) > 2 * f:
        r = np.linspace(0, 1, f)
        audio[:f] *= r
        audio[-f:] *= r[::-1]
    return audio.astype(np.float32)


def _goertzel_power(x, freq, fs):
    n = len(x)
    k = 2 * np.pi * freq / fs
    c = 2 * np.cos(k)
    s0 = s1 = s2 = 0.0
    for v in x:
        s0 = v + c * s1 - s2
        s2 = s1
        s1 = s0
    return s1 * s1 + s2 * s2 - c * s1 * s2


def demodulate(audio, fs=48000.0, baud=BAUD):
    """Near-ultrasound audio -> bytes (or None). Aligns on the sync preamble."""
    _need_numpy()
    x = np.asarray(audio, dtype=np.float64)
    spb = int(round(fs / baud))
    if len(x) < spb * (PREAMBLE_SYMS + 2):
        return None
    # find preamble start: first window where FSYNC dominates F0/F1
    hop = spb // 4
    start = None
    for i in range(0, len(x) - spb, hop):
        w = x[i:i + spb]
        ps = _goertzel_power(w, FSYNC, fs)
        if ps > 5 * (_goertzel_power(w, F0, fs) + _goertzel_power(w, F1, fs) + 1e-12):
            start = i
            break
    if start is None:
        return None
    # advance past the whole preamble
    payload0 = start + PREAMBLE_SYMS * spb
    bits = []
    i = payload0
    while i + spb <= len(x):
        w = x[i:i + spb]
        p0, p1 = _goertzel_power(w, F0, fs), _goertzel_power(w, F1, fs)
        if max(p0, p1) < 1e-9:
            break
        bits.append(1 if p1 > p0 else 0)
        i += spb
    if len(bits) < 16:
        return None
    by = np.packbits(np.array(bits[:len(bits) - (len(bits) % 8)], dtype=np.uint8)).tobytes()
    n = by[0]
    if len(by) < n + 2:
        return None
    payload, crc = by[1:1 + n], by[1 + n]
    if _crc8(payload) != crc:
        return None
    return payload


def _selftest():
    _need_numpy()
    print("Einstein ultrasonic data-over-sound self-test (software round-trip)")
    print("-" * 60)
    for msg in (b"KEYX:9f3a21", b"NET=CHARLIE CH=12 PIN=4471",
                b"status green, 3 souls safe"):
        aud = modulate(msg, fs=48000)
        # simulate a noisy room: add mild AWGN
        rx = aud + 0.01 * np.random.randn(len(aud))
        out = demodulate(rx, fs=48000)
        ok = out == msg
        print(f"  {'OK ' if ok else 'FAIL'}  {len(aud)/48000:5.2f}s  "
              f"tones {F0/1000:.1f}/{F1/1000:.1f} kHz  -> {out}")
    print("\nHonest note: acoustic, ~metres range, needs ~20 kHz-capable "
          "speaker/mic; wrap payloads with Beryl AES for confidentiality.")
    return 0


def main(argv):
    if "--selftest" in argv or not argv:
        return _selftest()
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
