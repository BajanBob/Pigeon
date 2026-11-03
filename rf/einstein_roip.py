# Einstein — VoIP <-> RF gateway (RoIP cross-patch) for COMMERCIAL / EmComm.
# Bridges a phone/computer VoIP endpoint to a radio: VoIP audio is played into
# the radio and keys PTT to transmit; received radio audio is sent back to the
# VoIP endpoint. A short handshake sets up the bridge before audio flows.
# Standard radio-over-IP cross-patch. Operate only on channels you are licensed
# for and identify per your licence; on amateur bands keep traffic clear text.
"""
Pieces:
  Handshake frames (clear text): b"ROIP" + JSON {op, from, to, session, ...}
    hello / accept / bye
  RoipGateway: ties a VoIP audio source/sink to a radio (audio + PTT driver).
    - VoIP->RF: when VoIP audio is present above a threshold, key PTT and play
      it to the radio; release PTT on silence (hang time).
    - RF->VoIP: when radio audio (squelch/VOX) is present, forward it to VoIP.
    - Half-duplex arbitration so both ends don't transmit at once.

Real deployment supplies: a VoIP endpoint (SIP/RTP or WebRTC), a radio audio
device (einstein_audio), and a PTT driver (einstein_ptt). This module is the
bridge logic + handshake; audio/PTT I/O are injected so it is testable offline.
"""

import json
import time

HS_MAGIC = b"ROIP"


# --------------------------------------------------------------------------
# Handshake
# --------------------------------------------------------------------------

def hs(op, frm, to, session, **extra):
    d = {"op": op, "from": frm, "to": to, "session": session}
    d.update(extra)
    return HS_MAGIC + json.dumps(d, separators=(",", ":")).encode("utf-8")


def parse_hs(blob):
    if not blob or blob[:4] != HS_MAGIC:
        return None
    try:
        return json.loads(blob[4:].decode("utf-8"))
    except Exception:
        return None


class Handshake:
    """Three-step bridge setup: hello -> accept -> (linked); bye tears down."""

    def __init__(self, me):
        self.me = me
        self.session = None
        self.peer = None
        self.state = "idle"       # idle | calling | linked

    def call(self, peer):
        self.peer, self.state = peer, "calling"
        self.session = f"{self.me}-{peer}-{int(time.time())}"
        return hs("hello", self.me, peer, self.session)

    def on_recv(self, blob):
        d = parse_hs(blob)
        if not d:
            return None
        op = d.get("op")
        if op == "hello" and d.get("to") == self.me:
            self.peer, self.session, self.state = d["from"], d["session"], "linked"
            return hs("accept", self.me, d["from"], d["session"])
        if op == "accept" and d.get("session") == self.session:
            self.state = "linked"
            return None
        if op == "bye":
            self.state = "idle"
            return None
        return None

    def bye(self):
        b = hs("bye", self.me, self.peer or "", self.session or "")
        self.state = "idle"
        return b


# --------------------------------------------------------------------------
# Bridge
# --------------------------------------------------------------------------

class RoipGateway:
    """Half-duplex VoIP<->RF bridge. Audio/PTT I/O are injected callables so the
    logic can be unit-tested without hardware or a network.

    ptt_key(bool)        key/unkey the radio
    play_to_radio(buf)   send audio buffer to the radio TX
    send_to_voip(buf)    send audio buffer to the VoIP endpoint
    """

    def __init__(self, me, ptt_key=None, play_to_radio=None, send_to_voip=None,
                 vox_threshold=0.02, hang_s=0.4):
        self.me = me
        self.ptt_key = ptt_key or (lambda on: None)
        self.play_to_radio = play_to_radio or (lambda buf: None)
        self.send_to_voip = send_to_voip or (lambda buf: None)
        self.vox = vox_threshold
        self.hang_s = hang_s
        self.hs = Handshake(me)
        self.tx = False            # currently transmitting on RF
        self._hang_until = 0.0
        self.rf_busy = False       # radio audio inbound (can't TX while RX)

    def _level(self, buf):
        if not buf:
            return 0.0
        try:
            import numpy as np
            x = np.asarray(buf, dtype=float)
            return float((x * x).mean()) ** 0.5
        except Exception:
            return sum(abs(v) for v in buf) / max(1, len(buf))

    # VoIP side: audio arriving from the phone -> maybe key PTT and play to radio
    def on_voip_audio(self, buf, now=None):
        now = time.time() if now is None else now
        if self.hs.state != "linked" or self.rf_busy:
            return
        if self._level(buf) >= self.vox:
            if not self.tx:
                self.tx = True
                self.ptt_key(True)
            self._hang_until = now + self.hang_s
            self.play_to_radio(buf)
        elif self.tx and now >= self._hang_until:
            self.tx = False
            self.ptt_key(False)

    # RF side: audio arriving from the radio -> forward to the phone
    def on_radio_audio(self, buf, now=None):
        if self.hs.state != "linked":
            return
        lvl = self._level(buf)
        self.rf_busy = lvl >= self.vox
        if self.tx:               # don't loop our own TX back
            return
        if self.rf_busy:
            self.send_to_voip(buf)

    def close(self):
        if self.tx:
            self.ptt_key(False)
            self.tx = False
        return self.hs.bye()


def _selftest():
    print("Einstein RoIP (VoIP<->RF) gateway self-test")
    print("-" * 46)
    log = {"ptt": [], "radio": 0, "voip": 0}
    gw = RoipGateway("GW1",
                     ptt_key=lambda on: log["ptt"].append(on),
                     play_to_radio=lambda b: log.__setitem__("radio", log["radio"] + 1),
                     send_to_voip=lambda b: log.__setitem__("voip", log["voip"] + 1))
    # handshake: a caller contacts the gateway
    caller = Handshake("PHONE")
    hello = caller.call("GW1")
    accept = gw.hs.on_recv(hello)
    caller.on_recv(accept)
    assert gw.hs.state == "linked" and caller.state == "linked", "handshake"
    print("  handshake: PHONE <-> GW1 linked")
    # VoIP audio -> keys PTT and plays to radio
    t = 100.0
    gw.on_voip_audio([0.3] * 160, now=t); t += 0.02
    gw.on_voip_audio([0.3] * 160, now=t); t += 0.02
    assert gw.tx and log["ptt"][0] is True and log["radio"] >= 2, "voip->rf TX"
    # silence past hang time -> unkey
    gw.on_voip_audio([0.0] * 160, now=t + 1.0)
    assert not gw.tx and log["ptt"][-1] is False, "unkey on silence"
    print(f"  VoIP->RF: keyed PTT, {log['radio']} frames to radio, released on silence")
    # radio audio -> forwarded to VoIP
    gw.on_radio_audio([0.3] * 160)
    assert log["voip"] >= 1, "rf->voip"
    print(f"  RF->VoIP: {log['voip']} frame(s) forwarded to the phone")
    bye = gw.close()
    assert parse_hs(bye)["op"] == "bye", "teardown"
    print("  teardown: bye sent")
    print("einstein_roip self-test OK (handshake, half-duplex bridge, PTT)")
    return 0


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv or len(sys.argv) == 1:
        raise SystemExit(_selftest())
    print(__doc__)
