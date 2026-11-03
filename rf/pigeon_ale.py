#!/usr/bin/env python3
"""
Pigeon ALE / Selcal / Beacon  —  Barrett-4050-inspired link layer  (AI-assisted, Claude)
=========================================================================================
Borrows the operational concepts of a commercial HF data terminal (e.g. Barrett 4050):
  * SELCAL  — selective calling: address a specific station; only it responds.
  * BEACON / SOUNDING — periodic transmissions others use to score link quality (LQA).
  * ALE     — Automatic Link Establishment: scan channels, sound, keep an LQA table,
              then call a station on the BEST channel and complete a handshake.

Built on the HOMER (AVIAN) waveform (pigeon_rf2): convolutional FEC + soft Viterbi +
interleave + CRC + Costas sync. Works on HF and VHF (audio into any SSB rig).

LEGAL: amateur radio forbids ENCRYPTION. This is CLEAR-TEXT signalling — addresses,
soundings and link handshakes in the open, exactly as ham ALE (MIL-STD-188-141 2G,
as used by HFLINK/pcALE) operates. It is NOT interoperable with a real Barrett/MIL-STD
ALE radio (that needs the standardized 8-FSK ALE waveform + Golay FEC); this is a
Pigeon-native ALE over the Pigeon waveform. Transmit only where licensed; identify.
"""
import struct, time
import numpy as np
import pigeon_rf2 as rf

# ---- generic HOMER frame carrier (raw 23-byte payload + CRC) --------------------
P0 = rf.P0
def _frame_bytes(payload):
    body = (payload[:P0] + bytes(P0 - len(payload))) if len(payload) < P0 else payload[:P0]
    return body + struct.pack(">H", rf.crc16(body))

def encode_payload(payload):
    coded = rf.conv_encode(rf._b2bits(_frame_bytes(payload)))
    il, n = rf._il(list(coded), 16)
    while len(il) % 4: il.append(0)
    data = [il[i] | (il[i+1] << 1) | (il[i+2] << 2) | (il[i+3] << 3) for i in range(0, len(il), 4)]
    syms = rf.SYNC + data
    t = np.arange(rf.SYMLEN) / rf.FS; out = [np.zeros(rf.LEAD)]; ph = 0.0
    for s in syms:
        f = rf.TONE_HZ[s]; out.append(np.sin(2*np.pi*f*t + ph)); ph = (ph + 2*np.pi*f*rf.SYMLEN/rf.FS) % (2*np.pi)
    y = np.concatenate(out); y *= 0.6 / (np.max(np.abs(y)) + 1e-9)
    return y.astype(np.float64)

def _decode_payload_at(x, start):
    pos = start + len(rf.SYNC)*rf.SYMLEN
    if pos + rf.NDATA*rf.SYMLEN > len(x): return None
    soft = []
    for i in range(rf.NDATA):
        soft += rf._soft_bits(rf._powers(x, pos + i*rf.SYMLEN))
    de = rf._dil(soft[:rf.IL_LEN], rf.NCODED, 16)
    try: info = rf.viterbi_soft(np.array(de, float))
    except Exception: return None
    data = rf._bits2b([1 if b else 0 for b in info])
    if len(data) < P0 + 2: return None
    body = data[:P0]; got = struct.unpack(">H", data[P0:P0+2])[0]
    if rf.crc16(body) != got: return None
    return body

def decode_payload(samples):
    x = np.asarray(samples, float)
    hi = len(x) - len(rf.SYNC)*rf.SYMLEN; step = rf.SYMLEN // 4
    cands = sorted(((rf._sync_score(x, p), p) for p in range(0, max(1, hi), step)), key=lambda c: -c[0])
    tried = set()
    for _, cpos in cands[:12]:
        for off in range(-step, step+1, rf.SYMLEN // 16):
            p = cpos + off
            if p < 0 or p in tried: continue
            tried.add(p)
            r = _decode_payload_at(x, p)
            if r is not None: return r
    return None

# ---- ALE frame format (clear text) ---------------------------------------------
# byte0: type   1=CALL 2=ACK 3=SOUND(beacon) 4=LINKED
# 1..4 : src address (4 ASCII, padded)   5..8: dst address   9: channel  10: LQA(0..255)
# 11   : seq
TYPE = {"CALL":1, "ACK":2, "SOUND":3, "LINKED":4}
NAME = {v:k for k,v in TYPE.items()}
def _addr(a): return (a.upper().encode("ascii")[:4] + b"\x00\x00\x00\x00")[:4]
def _astr(b): return b.rstrip(b"\x00").decode("ascii", "ignore")

def make_frame(kind, src, dst="", chan=0, lqa=0, seq=0):
    return bytes([TYPE[kind]]) + _addr(src) + _addr(dst) + bytes([chan & 0xFF, lqa & 0xFF, seq & 0xFF])
def parse_frame(body):
    if not body or body[0] not in NAME: return None
    return {"type": NAME[body[0]], "src": _astr(body[1:5]), "dst": _astr(body[5:9]),
            "chan": body[9], "lqa": body[10], "seq": body[11]}

# ---- LQA scoring from a received frame's SNR -----------------------------------
def snr_estimate(x):
    """Rough SNR (dB) of a received HOMER frame from sync-tone energy vs the rest."""
    hi = len(x) - len(rf.SYNC)*rf.SYMLEN; step = rf.SYMLEN // 4
    best = max((rf._sync_score(x, p) for p in range(0, max(1, hi), step)), default=0)
    # sync_score ~ sum over 16 sync symbols of (tone power / total). 1.0 per symbol = perfect.
    frac = best / len(rf.SYNC)
    return round(10*np.log10(max(1e-3, frac/(1-min(0.99, frac)))), 1)  # monotone LQA proxy

# ---- ALE station controller (operational logic; I/O is pluggable) --------------
class Station:
    def __init__(self, address, channels, send=None, recv=None):
        self.addr = address.upper()[:4]
        self.channels = list(channels)            # e.g. ["14.1086","18.1060","21.0966"] (MHz) or VHF
        self.send = send or (lambda ch, samples: None)   # hook: key rig on ch, play samples
        self.recv = recv or (lambda ch, secs: None)      # hook: listen on ch -> samples|None
        self.lqa = {}                             # (peer,chan) -> score dB
        self.seq = 0

    def sound(self):
        """Beacon/sounding on every channel so peers can score us (and we them)."""
        for ch in range(len(self.channels)):
            self.seq = (self.seq + 1) & 0xFF
            self.send(ch, encode_payload(make_frame("SOUND", self.addr, chan=ch, seq=self.seq)))

    def scan(self, dwell=2.0):
        """Listen across channels; log LQA of any SOUND/CALL heard."""
        for ch in range(len(self.channels)):
            x = self.recv(ch, dwell)
            if x is None: continue
            body = decode_payload(x); fr = parse_frame(body) if body else None
            if fr:
                self.lqa[(fr["src"], ch)] = snr_estimate(x)
                if fr["type"] == "CALL" and fr["dst"] == self.addr:
                    self.send(ch, encode_payload(make_frame("ACK", self.addr, fr["src"], ch,
                              lqa=int(max(0, min(255, snr_estimate(x)+30))), seq=fr["seq"])))

    def best_channel(self, peer):
        opts = [(ch, s) for (p, ch), s in self.lqa.items() if p == peer]
        return max(opts, key=lambda o: o[1])[0] if opts else 0

    def call(self, dst, listen=None):
        """ALE call: pick the best channel from LQA history, CALL, await ACK -> LINKED."""
        listen = listen or (lambda ch, secs: self.recv(ch, secs))
        ch = self.best_channel(dst); self.seq = (self.seq + 1) & 0xFF
        self.send(ch, encode_payload(make_frame("CALL", self.addr, dst, ch, seq=self.seq)))
        x = listen(ch, 4.0)
        if x is not None:
            fr = parse_frame(decode_payload(x) or b"")
            if fr and fr["type"] == "ACK" and fr["dst"] == self.addr and fr["src"] == dst:
                self.send(ch, encode_payload(make_frame("LINKED", self.addr, dst, ch, seq=self.seq)))
                return {"linked": True, "channel": ch, "freq": self.channels[ch], "peer": dst}
        return {"linked": False, "channel": ch}

# ---- self-test: two stations over a simulated channel --------------------------
if __name__ == "__main__":
    print("Pigeon ALE self-test (clear text). Frame carrier + selcal + ALE handshake.\n")
    rng = np.random.default_rng(0)

    # round-trip a frame through noise
    f = make_frame("CALL", "8P6N", "G4AB", chan=2, seq=7)
    y = encode_payload(f)
    y += rng.normal(0, np.sqrt(np.mean(y[rf.LEAD:]**2))*3.0, len(y))   # noisy channel
    got = parse_frame(decode_payload(y) or b"")
    print("frame round-trip through noise:", got)

    # ALE sim: shared "ether" per channel; B is reachable best on channel 1
    ether = {}
    chans = ["14.1086", "18.1060", "21.0966"]
    gains = [0.25, 1.0, 0.5]       # channel 1 is the good one
    def mk_send(label):
        def _s(ch, samples):
            g = gains[ch]; s = g*samples + rng.normal(0, np.sqrt(np.mean(samples[rf.LEAD:]**2))*(1.2 if g>0.6 else 4.0), len(samples))
            ether[ch] = s
        return _s
    def mk_recv():
        def _r(ch, secs): return ether.get(ch)
        return _r
    A = Station("8P6N", chans, send=mk_send("A"), recv=mk_recv())
    B = Station("G4AB", chans, send=mk_send("B"), recv=mk_recv())

    A.sound(); B.scan()          # A beacons; B scores A per channel
    B.sound(); A.scan()          # B beacons; A scores B per channel
    print("A's LQA table (peer,chan)->dB:", {k: round(float(v),1) for k, v in A.lqa.items()})
    print("A picks best channel for G4AB:", A.best_channel("G4AB"), "->", chans[A.best_channel("G4AB")], "MHz")
    # concurrency: while A waits for the ACK, B is scanning and answers the CALL it hears
    res = A.call("G4AB", listen=lambda ch, secs: (B.scan(), ether.get(ch))[1])
    print("ALE call result:", res)
