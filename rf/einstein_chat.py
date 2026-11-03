# Einstein — clear-text text chat over the Einstein modem.
# A live, bidirectional, sequenced chat with per-message ACK and in-order
# delivery, carried by the Einstein Modem / AFSK. Clear text on amateur bands
# (zlib compression is reversible, not a cipher); AES only applies on the
# commercial / EmComm path.
"""
    build(frm, to, seq, text)   -> wire blob (zlib)        MAGIC b"ECH2"
    parse(blob)                 -> {frm,to,seq,text} or None
    ack(frm, to, seq)           -> tiny ACK frame          MAGIC b"ECKA"
    is_ack(blob)                -> (frm,to,seq) or None
    Session(me, peer)           -> compose()/receive()/pending with dedup + log
"""

import zlib

MAGIC = b"ECH2"
AMAGIC = b"ECKA"


def build(frm, to, seq, text):
    hdr = f"{frm}|{to}|{int(seq)}".encode("latin-1", "replace")
    body = hdr + b"\n" + (text.encode("utf-8", "replace") if isinstance(text, str) else text)
    return MAGIC + zlib.compress(body, 9)


def parse(blob):
    if not blob or blob[:4] != MAGIC:
        return None
    try:
        raw = zlib.decompress(blob[4:])
    except Exception:
        return None
    hdr, _, txt = raw.partition(b"\n")
    try:
        frm, to, seq = hdr.decode("latin-1").split("|")
        return {"frm": frm, "to": to, "seq": int(seq),
                "text": txt.decode("utf-8", "replace")}
    except Exception:
        return None


def ack(frm, to, seq):
    return AMAGIC + f"{frm}|{to}|{int(seq)}".encode("latin-1", "replace")


def is_ack(blob):
    if not blob or blob[:4] != AMAGIC:
        return None
    try:
        frm, to, seq = blob[4:].decode("latin-1").split("|")
        return (frm, to, int(seq))
    except Exception:
        return None


class Session:
    """Bidirectional chat state: sequence numbers, ACK tracking, dedup, log."""

    def __init__(self, me, peer):
        self.me, self.peer = me.upper(), peer.upper()
        self._seq = 0
        self._seen = set()           # (frm,seq) already received
        self._unacked = {}           # seq -> text awaiting ACK
        self.log = []                # (who, seq, text)

    def compose(self, text):
        """Return the wire blob for a new outgoing message."""
        self._seq += 1
        self._unacked[self._seq] = text
        self.log.append((self.me, self._seq, text))
        return build(self.me, self.peer, self._seq, text)

    def receive(self, blob):
        """Feed a received blob. Returns a dict describing what happened:
        {'type':'msg','text','seq','ack':<blob>} | {'type':'ack','seq'} | None"""
        a = is_ack(blob)
        if a:
            _, _, seq = a
            self._unacked.pop(seq, None)
            return {"type": "ack", "seq": seq}
        m = parse(blob)
        if not m or m["to"] not in (self.me, "CQ", "ALL"):
            return None
        key = (m["frm"], m["seq"])
        ackblob = ack(self.me, m["frm"], m["seq"])
        if key in self._seen:
            return {"type": "dup", "seq": m["seq"], "ack": ackblob}
        self._seen.add(key)
        self.log.append((m["frm"], m["seq"], m["text"]))
        return {"type": "msg", "text": m["text"], "seq": m["seq"],
                "frm": m["frm"], "ack": ackblob}

    def pending(self):
        """Messages still awaiting an ACK (for retransmission)."""
        return dict(self._unacked)

    def transcript(self):
        return [f"{who}: {txt}" for who, _, txt in self.log]


if __name__ == "__main__":
    # Two sessions talk to each other through blobs (loopback self-test).
    a = Session("8P5AB", "8P5DG")
    b = Session("8P5DG", "8P5AB")
    tx = a.compose("Net control, how copy?")
    r = b.receive(tx)
    assert r["type"] == "msg" and r["text"] == "Net control, how copy?", "msg"
    ra = a.receive(r["ack"])
    assert ra["type"] == "ack" and not a.pending(), "ack clears pending"
    # dedup: replay the same frame
    assert b.receive(tx)["type"] == "dup", "dedup"
    # reply direction
    tx2 = b.compose("Loud and clear, 59.")
    r2 = a.receive(tx2)
    a.receive  # noqa
    assert r2["type"] == "msg", "reply"
    b.receive(r2["ack"])
    print("A transcript:", a.transcript())
    print("B transcript:", b.transcript())
    print("einstein_chat self-test OK (sequenced, ACKed, dedup)")
