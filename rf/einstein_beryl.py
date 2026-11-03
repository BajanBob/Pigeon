# Einstein — Beryl: LPI direct-sequence spread spectrum (COMMERCIAL / EmComm).
#
# SCOPE & HONESTY (read this):
# - Beryl is for LICENSED COMMERCIAL / EmComm channels only: 148–174 MHz.
#   It is BAND-GATED and refuses amateur frequencies. Amateur rules forbid
#   obscuring the meaning of a transmission, so Beryl is never used on ham RF.
# - Beryl provides LOW PROBABILITY OF INTERCEPT (LPI) + anti-jam robustness by
#   spreading the signal below the noise floor, and CONFIDENTIALITY via the same
#   AES-256-GCM used by the commercial mode. It is NOT "undetectable": a
#   determined wideband SIGINT receiver using energy integration or
#   cyclostationary feature detection can still detect the energy (see the
#   square-root law of covert communication). We do not claim otherwise.
# - Operators must identify per their licence and operate only on channels they
#   are authorised to use. LPI is a robustness/interception property, not a
#   licence to hide from regulators.
"""
Direct-sequence spread spectrum (DSSS):
  pn_code(sf)                 maximal-length PN spreading code (+/-1), length sf
  spread(bits, sf)           -> chips (+/-1), pn
  despread(chips, pn, nbits) -> bits, correlation
  processing_gain_db(sf)     10*log10(sf)
  modulate(bytes, sf, ...)   payload -> BPSK passband audio (optional carrier)
  demodulate(audio, ...)     passband audio -> payload bytes
Optional confidentiality:
  encrypt(plaintext, key)    AES-256-GCM (needs 'cryptography'); else raises
  decrypt(blob, key)

Band gate:
  assert_commercial_band(freq_mhz)   148–174 MHz only, else ValueError
"""

import sys

try:
    import numpy as np
except ImportError:
    np = None

COMMERCIAL_BAND_MHZ = (148.0, 174.0)


def _need_numpy():
    if np is None:
        raise RuntimeError("Beryl needs numpy (pip install numpy)")


def assert_commercial_band(freq_mhz):
    """Beryl is confined to licensed commercial / EmComm VHF channels."""
    lo, hi = COMMERCIAL_BAND_MHZ
    if not (lo <= float(freq_mhz) <= hi):
        raise ValueError(
            f"Beryl LPI is restricted to licensed commercial channels "
            f"{lo:.0f}–{hi:.0f} MHz; {freq_mhz} MHz refused. "
            f"Never on amateur bands (clear text only there).")
    return True


# --------------------------------------------------------------------------
# PN spreading code (maximal-length LFSR / m-sequence)
# --------------------------------------------------------------------------

def _mseq(nbits, taps, seed=1):
    """Maximal-length sequence of length 2**nbits - 1 (bits 0/1)."""
    reg = seed & ((1 << nbits) - 1)
    if reg == 0:
        reg = 1
    out = []
    for _ in range((1 << nbits) - 1):
        out.append(reg & 1)
        fb = 0
        for t in taps:
            fb ^= (reg >> (t - 1)) & 1
        reg = (reg >> 1) | (fb << (nbits - 1))
    return np.array(out, dtype=np.int8)


# a few maximal-length tap sets (feedback polynomials)
_TAPS = {7: [7, 6], 9: [9, 5], 10: [10, 7], 11: [11, 9], 13: [13, 12, 11, 8]}


def pn_code(sf, seed=1):
    """Bipolar (+/-1) spreading code of length sf from an m-sequence."""
    _need_numpy()
    # pick the smallest m-sequence whose length >= sf (else the largest, tiled)
    nbits = max(_TAPS)
    for n in sorted(_TAPS):
        if (1 << n) - 1 >= sf:
            nbits = n
            break
    base = _mseq(nbits, _TAPS[nbits], seed)
    code = np.resize(base, sf)
    return 1.0 - 2.0 * code.astype(np.float64)   # 0->+1, 1->-1


def processing_gain_db(sf):
    _need_numpy()
    return float(10 * np.log10(sf))


# --------------------------------------------------------------------------
# Spread / despread
# --------------------------------------------------------------------------

def _bytes_to_bits(data):
    return np.unpackbits(np.frombuffer(bytes(data), dtype=np.uint8))


def _bits_to_bytes(bits):
    bits = np.asarray(bits, dtype=np.uint8)
    bits = bits[:len(bits) - (len(bits) % 8)]
    return np.packbits(bits).tobytes()


def spread(bits, sf, seed=1):
    """BPSK-spread each data bit by the PN code (chips are +/-1)."""
    _need_numpy()
    d = 1.0 - 2.0 * np.asarray(bits, dtype=np.float64)   # 0->+1, 1->-1
    pn = pn_code(sf, seed)
    chips = (d[:, None] * pn[None, :]).reshape(-1)
    return chips, pn


def despread(chips, pn, nbits):
    """Correlate each symbol against the PN code and decide the bit."""
    _need_numpy()
    sf = len(pn)
    c = np.asarray(chips, dtype=np.float64)[:nbits * sf].reshape(nbits, sf)
    corr = (c * pn[None, :]).sum(1)
    bits = (corr < 0).astype(int)                       # +corr -> 0, -corr -> 1
    return bits, corr


# --------------------------------------------------------------------------
# Passband modem (BPSK on a carrier)
# --------------------------------------------------------------------------

def modulate(payload, sf=255, fs=48000.0, fc=12000.0, chip_rate=8000.0,
             level=0.5, seed=1):
    """Payload bytes -> float32 BPSK-DSSS passband audio."""
    _need_numpy()
    bits = _bytes_to_bits(payload)
    chips, _ = spread(bits, sf, seed)
    spc = int(round(fs / chip_rate))
    base = np.repeat(chips, spc)
    t = np.arange(len(base)) / fs
    return (level * base * np.sin(2 * np.pi * fc * t)).astype(np.float32)


def demodulate(audio, nbytes, sf=255, fs=48000.0, fc=12000.0, chip_rate=8000.0,
               seed=1):
    """Passband audio -> payload bytes (coherent BPSK, matched to chip_rate)."""
    _need_numpy()
    x = np.asarray(audio, dtype=np.float64)
    t = np.arange(len(x)) / fs
    bb = x * np.sin(2 * np.pi * fc * t)                 # mix down
    spc = int(round(fs / chip_rate))
    nchips = len(bb) // spc
    chips = bb[:nchips * spc].reshape(nchips, spc).mean(1)   # integrate per chip
    pn = pn_code(sf, seed)
    nbits = min(nchips // sf, nbytes * 8)
    bits, _ = despread(chips, pn, nbits)
    return _bits_to_bytes(bits)[:nbytes]


# --------------------------------------------------------------------------
# Optional confidentiality (commercial only) — AES-256-GCM
# --------------------------------------------------------------------------

def _aes_key(passphrase, salt=b"einstein-beryl-v1"):
    import hashlib
    return hashlib.scrypt(passphrase.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)


def encrypt(plaintext, passphrase):
    """AES-256-GCM. Commercial/EmComm channels only. Needs 'cryptography'."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except Exception as e:
        raise RuntimeError("encryption needs the 'cryptography' package "
                           "(pip install cryptography). Commercial band only.") from e
    import os
    key = _aes_key(passphrase)
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext if isinstance(plaintext, bytes)
                             else plaintext.encode(), None)
    return b"BERYL1" + nonce + ct


def decrypt(blob, passphrase):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    assert blob[:6] == b"BERYL1", "not a Beryl ciphertext"
    key = _aes_key(passphrase)
    return AESGCM(key).decrypt(blob[6:18], blob[18:], None)


# --------------------------------------------------------------------------
# Self-test — honest demonstration of sub-noise LPI operation
# --------------------------------------------------------------------------

def _awgn(x, snr_db):
    p = np.mean(x * x)
    n = np.sqrt(p / (10 ** (snr_db / 10)))
    return x + n * np.random.randn(len(x))


def _selftest():
    _need_numpy()
    print("Beryl LPI spread-spectrum self-test")
    print("-" * 52)
    # band gate
    try:
        assert_commercial_band(145.0); print("BAND GATE FAILED (145 allowed!)"); return 1
    except ValueError:
        print("band gate: 145.000 MHz (amateur) correctly refused")
    assert_commercial_band(154.0); print("band gate: 154.000 MHz (commercial) allowed")
    # spreading gain vs chip-level SNR
    rng = np.random.default_rng(1)
    nbits = 2000
    for sf in (31, 127, 511):
        bits = rng.integers(0, 2, nbits)
        chips, pn = spread(bits, sf)
        # add noise at a NEGATIVE chip SNR (signal below the noise floor)
        chip_snr = -9.0
        rx = _awgn(chips, chip_snr)
        got, _ = despread(rx, pn, nbits)
        ber = np.mean(got != bits)
        print(f"  sf={sf:4d}  Gp={processing_gain_db(sf):4.1f} dB  "
              f"chip SNR={chip_snr:+.0f} dB  ->  BER={ber:.4f}")
    # passband modem round-trip (clean)
    msg = b"EMCOMM NET CTRL: status green"
    aud = modulate(msg, sf=127, fs=48000, fc=12000, chip_rate=6000)
    out = demodulate(aud, len(msg), sf=127, fs=48000, fc=12000, chip_rate=6000)
    ok = out == msg
    print(f"  passband modem round-trip: {'OK' if ok else 'FAIL'} "
          f"({len(aud)/48000:.1f}s audio)")
    # optional encryption
    try:
        blob = encrypt("status green", "unit-net-passphrase-123456")
        dec = decrypt(blob, "unit-net-passphrase-123456").decode()
        print(f"  AES-256-GCM: OK ({'status green'==dec})")
    except RuntimeError as e:
        print(f"  AES-256-GCM: skipped ({e})")
    print("\nHonest note: processing gain lets Beryl decode below the noise "
          "floor (LPI), but that is robustness/low-interceptability — NOT "
          "undetectability. Commercial 148–174 MHz only; identify per licence.")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv or not argv:
        return _selftest()
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
