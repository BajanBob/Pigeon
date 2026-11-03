#!/usr/bin/env python3
"""
Einstein Email — messaging & RF-email layer over the Einstein modem
===================================================================
A clear-text (amateur-legal) store-and-forward message layer, à la Winlink but
Einstein-native. Builds compressed, framed, CRC-protected messages addressed by
callsign/Selcall, chunks them to modem frames, and runs a Stop-and-Wait ARQ with
selective retransmit of failed blocks. AI-assisted (Claude).

NOTE: amateur rules forbid encryption of the message content; zlib COMPRESSION
is a published, reversible transform (not a cipher) and is permitted — it carries
no key and anyone may decode it. No AES, no scrambling on the RF path, ever.
"""
import zlib, struct, time
import numpy as np
import einstein_modem as em

MAGIC = b"EE1"                      # Einstein Email v1
def _crc16(b):
    c=0xFFFF
    for x in b:
        c^=x<<8
        for _ in range(8): c=((c<<1)^0x1021)&0xFFFF if c&0x8000 else (c<<1)&0xFFFF
    return c

def build_message(frm, to, subject, body, send_time=None):
    """Compose an RF-email message -> compressed clear-text byte blob."""
    t = int(send_time or time.time())
    hdr = "\n".join([f"FROM:{frm}", f"TO:{to}", f"SUBJ:{subject}",
                     f"UTC:{t}", f"LEN:{len(body.encode())}"]).encode()
    raw = hdr + b"\n\n" + body.encode()
    comp = zlib.compress(raw, 9)
    blob = MAGIC + struct.pack(">I", len(raw)) + comp
    return blob

def parse_message(blob):
    if blob[:3]!=MAGIC: raise ValueError("not an Einstein Email blob")
    rawlen = struct.unpack(">I", blob[3:7])[0]
    raw = zlib.decompress(blob[7:])
    assert len(raw)==rawlen
    head, _, body = raw.partition(b"\n\n")
    meta = dict(l.split(":",1) for l in head.decode().splitlines() if ":" in l)
    # body is after the blank line that followed the header block
    txt = raw.decode(); body = txt.split("\n\n",1)[1] if "\n\n" in txt else ""
    return meta, body

# ---- block framing for ARQ: split blob into numbered blocks ----
def to_blocks(blob, block_bytes=48):
    n = (len(blob)+block_bytes-1)//block_bytes
    blocks=[]
    for i in range(n):
        chunk = blob[i*block_bytes:(i+1)*block_bytes]
        frame = struct.pack(">HH", i, n) + chunk
        frame += struct.pack(">H", _crc16(frame))
        blocks.append(frame)
    return blocks

def check_block(frame):
    if frame is None or len(frame) < 6: return None
    body, crc = frame[:-2], struct.unpack(">H", frame[-2:])[0]
    if _crc16(body)!=crc: return None
    i,n = struct.unpack(">HH", body[:4]); return i,n,body[4:]

# ---- Stop-and-Wait / selective-ARQ simulation over the modem+channel ----
def send_recv(blob, profile="STANDARD", channel=None, max_rounds=6, block_bytes=48):
    """Transmit blob via blocks; receiver NAKs missing/corrupt; TX resends.
    channel(audio)->audio adds impairment. Returns (ok, rounds, received_blob)."""
    blocks = to_blocks(blob, block_bytes)
    n = len(blocks); have = {}
    rounds = 0
    need = set(range(n))
    while need and rounds < max_rounds:
        rounds += 1
        for i in sorted(need):
            y, meta = em.modulate(blocks[i], profile)
            r = channel(y) if channel else y
            got = em.demodulate(r, profile, meta)
            if got is not None:
                res = check_block(got)
                if res and res[0]==i:
                    have[i]=res[2]
        need = set(range(n)) - set(have)
    if need: return False, rounds, None
    rx = b"".join(have[i] for i in range(n))
    # trim to real length (blocks are fixed, last one may be short already)
    return True, rounds, rx[:len(blob)]

if __name__=="__main__":
    print("Einstein Email self-test\n")
    blob = build_message("8P6NH","KV4FZ","Field report",
        "All stations: Einstein Email over HF is operational. "
        "Duct forecast favourable, 6 m open to the north. 73 de 8P6NH.")
    print(f"  message blob: {len(blob)} bytes compressed")
    meta, body = parse_message(blob)
    print(f"  round-trip header FROM={meta.get('FROM')} TO={meta.get('TO')} SUBJ={meta.get('SUBJ')}")
    print(f"  body ok: {body.strip().startswith('All stations')}")
    # clean-channel ARQ
    ok,rounds,rx = send_recv(blob, "PRO")
    print(f"  ARQ clean (PRO): ok={ok} rounds={rounds} match={rx==blob}")
    # lossy channel: drop ~30% of frames at random
    import numpy as np
    rng=np.random.default_rng(3)
    def lossy(y):
        if rng.random()<0.3: return y*0  # simulate a lost/over-driven frame
        return y + np.sqrt(np.mean(y**2)/50)*rng.standard_normal(len(y))
    ok,rounds,rx = send_recv(blob, "STANDARD", lossy)
    print(f"  ARQ 30%-loss (STD): ok={ok} rounds={rounds} match={rx==blob}")
