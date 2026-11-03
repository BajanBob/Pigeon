# Einstein — native PTT / CAT drivers.
# Ported from the companion Tradewind project (Brandon St Rose 8P5DG,
# Kammie Holder 8P5AB), MIT License. Gives Einstein its own keying and
# tuning so it stands alone on a PC/Pi without an external helper.
#
# Keying only — no RF content is altered here. All amateur traffic stays
# clear text; these drivers just assert PTT and (for CAT links) set the
# frequency / mode.
"""
PTT drivers:

  VOX ................ no wiring (interface keys on audio)      -> PTT (base)
  Serial RTS / DTR ... Digirig, AIOC, Icom USB, home-brew       -> SerialPTT
  CM108 GPIO ......... CM108/CM119 USB fobs (Linux /dev/hidraw) -> CM108PTT
  Hamlib rigctld ..... any radio Hamlib supports (CAT PTT+tune) -> RigctldPTT
  Icom CI-V .......... IC-9100/705/9700/7100/7300/7610 (PTT+tune)-> CivPTT
  Yaesu CAT .......... FT-991A/710/FTDX10/101 (PTT+tune)         -> YaesuCatPTT

make_ptt(kind, **opts) builds the right one from a radio preset.
"""

import os
import time
import socket


class PTT:
    name = "VOX"
    can_tune = False      # True when the link can also set frequency / mode (CAT)

    def open(self): pass
    def key(self, on: bool): pass
    def close(self): pass


class SerialPTT(PTT):
    """RTS or DTR on a serial port (Icom CI-V USB, Yaesu enhanced COM,
    Digirig, AIOC, home-brew transistor interfaces)."""

    def __init__(self, port, line="RTS", invert=False):
        self.port, self.line, self.invert = port, line.upper(), invert
        self.name = f"{self.line} on {port}"
        self.ser = None

    def open(self):
        import serial  # pyserial
        self.ser = serial.Serial()
        self.ser.port = self.port
        self.ser.rts = self.ser.dtr = False   # don't key up on open
        self.ser.open()
        self.key(False)

    def key(self, on):
        v = bool(on) ^ self.invert
        if self.line == "RTS":
            self.ser.rts, self.ser.dtr = v, False
        else:
            self.ser.dtr, self.ser.rts = v, False

    def close(self):
        if self.ser:
            try:
                self.key(False)
                self.ser.close()
            finally:
                self.ser = None


class CM108PTT(PTT):
    """GPIO on a CM108/CM119 USB audio chip (Digirig-Lite, AllStar fobs,
    many home-made interfaces). Linux: /dev/hidrawN."""

    def __init__(self, device="/dev/hidraw0", gpio=3):
        self.device, self.gpio = device, int(gpio)
        self.name = f"CM108 GPIO{gpio} on {device}"
        self.fd = None

    def open(self):
        self.fd = os.open(self.device, os.O_WRONLY)
        self.key(False)

    def key(self, on):
        bit = 1 << (self.gpio - 1)
        os.write(self.fd, bytes([0, 0, bit, bit if on else 0, 0]))

    def close(self):
        if self.fd is not None:
            try:
                self.key(False)
            finally:
                os.close(self.fd)
                self.fd = None


class RigctldPTT(PTT):
    """CAT PTT (and frequency / mode) through Hamlib's rigctld."""
    can_tune = True

    def __init__(self, host="127.0.0.1", port=4532):
        self.host, self.port = host, int(port)
        self.name = f"rigctld {host}:{port}"

    def open(self): pass

    def _ask(self, cmd):
        with socket.create_connection((self.host, self.port), timeout=5) as s:
            s.sendall(cmd.encode() + b"\n")
            time.sleep(0.15)
            return s.recv(256).decode(errors="replace")

    def key(self, on):
        self._ask("T 1" if on else "T 0")

    def read_state(self):
        f = self._ask("f").split()
        m = self._ask("m").split()
        return {"hz": int(f[0]) if f and f[0].isdigit() else None,
                "mode": m[0] if m and not m[0].startswith("RPRT") else None,
                "pb": m[1] if len(m) > 1 and m[1].lstrip("-").isdigit() else "0"}

    def tune(self, hz):
        r = self._ask(f"F {int(hz)}")
        if "RPRT -" in r:
            raise IOError(f"rigctld refused frequency ({r.strip()})")
        if "RPRT -" in self._ask("M PKTFM 0"):      # FM data mode if the radio has one
            self._ask("M FM 0")

    def restore(self, st):
        if st.get("hz"):
            self._ask(f"F {st['hz']}")
        if st.get("mode"):
            self._ask(f"M {st['mode']} {st.get('pb', '0')}")

    def close(self): pass


# ----- Icom CI-V helpers -----

def _civ_addr(addr):
    return int(str(addr), 16) if isinstance(addr, str) else int(addr)


def civ_frame(addr, payload):
    """FE FE <radio> E0 <payload> FD"""
    return bytes([0xFE, 0xFE, _civ_addr(addr) & 0xFF, 0xE0]) + bytes(payload) + b"\xFD"


def civ_ptt_command(addr, on):
    """Icom CI-V 'transmit on/off' (command 1C 00)."""
    return civ_frame(addr, [0x1C, 0x00, 0x01 if on else 0x00])


def hz_to_civ_bcd(hz):
    """Frequency in Hz -> 5 CI-V BCD bytes, least significant pair first.
    144.390 MHz -> 00 00 39 44 01"""
    s = f"{int(hz):010d}"
    return bytes((int(s[i]) << 4) | int(s[i + 1]) for i in range(8, -1, -2))


def civ_bcd_to_hz(b):
    return int("".join(f"{x:02x}" for x in reversed(bytes(b[:5]))))


def civ_replies(data, addr):
    """Payloads of frames the radio sent to the PC (skips our own echo)."""
    a = _civ_addr(addr)
    out = []
    for part in bytes(data).split(b"\xFE\xFE")[1:]:
        end = part.find(b"\xFD")
        if end >= 2 and part[0] == 0xE0 and part[1] == a:
            out.append(part[2:end])
    return out


class _CatSerialPTT(PTT):
    """Base for PTT commands sent over a radio's CAT serial port."""

    def __init__(self, port, baud):
        self.port, self.baud = port, int(baud)
        self.ser = None

    def open(self):
        import serial
        self.ser = serial.Serial()
        self.ser.port, self.ser.baudrate, self.ser.timeout = self.port, self.baud, 0.3
        self.ser.rts = self.ser.dtr = False   # never key up via RTS/DTR by accident
        self.ser.open()
        self.key(False)

    def _cmd(self, on):
        raise NotImplementedError

    def key(self, on):
        self.ser.reset_input_buffer()
        self.ser.write(self._cmd(on))
        self.ser.flush()
        time.sleep(0.05)
        self.ser.read(64)  # discard echo / acknowledgement

    def close(self):
        if self.ser:
            try:
                self.key(False)
            finally:
                self.ser.close()
                self.ser = None


class CivPTT(_CatSerialPTT):
    """Icom CI-V PTT, frequency and mode over USB or a CI-V cable
    (IC-9100, IC-7100, IC-705, IC-9700, IC-7300, IC-7610...)."""
    can_tune = True

    def __init__(self, port, baud=9600, addr="7C"):
        super().__init__(port, baud)
        self.addr = addr
        self.name = f"CI-V {addr}h on {port}"

    def _cmd(self, on):
        return civ_ptt_command(self.addr, on)

    def _ask(self, payload):
        """Send one CI-V command; return the radio's reply payload (or None)."""
        self.ser.reset_input_buffer()
        self.ser.write(civ_frame(self.addr, payload))
        self.ser.flush()
        data, t0 = b"", time.time()
        while time.time() - t0 < 0.6:
            data += self.ser.read(64)
            r = civ_replies(data, self.addr)
            if r:
                return r[0]
        return None

    def read_state(self):
        st = {}
        r = self._ask([0x03])                         # read operating frequency
        if r and r[0] == 0x03 and len(r) >= 6:
            st["hz"] = civ_bcd_to_hz(r[1:6])
        r = self._ask([0x04])                         # read mode + filter
        if r and r[0] == 0x04 and len(r) >= 3:
            st["mode"] = [r[1], r[2]]
        r = self._ask([0x1A, 0x06])                   # read DATA mode
        if r and r[:2] == b"\x1A\x06" and len(r) >= 3:
            st["data"] = list(r[2:])
        return st

    def tune(self, hz):
        r = self._ask([0x05] + list(hz_to_civ_bcd(hz)))
        if r != b"\xFB":
            raise IOError("radio did not accept the frequency (check CI-V address and baud rate)"
                          if r is None else "radio refused the frequency - is it in this radio's range?")
        self._ask([0x06, 0x05, 0x01])                 # FM, filter 1
        if self._ask([0x1A, 0x06, 0x01, 0x01]) != b"\xFB":   # DATA mode on (FM-D)
            self._ask([0x1A, 0x06, 0x01])             # radios that take a single data byte

    def restore(self, st):
        if st.get("hz"):
            self._ask([0x05] + list(hz_to_civ_bcd(st["hz"])))
        if st.get("mode"):
            self._ask([0x06] + st["mode"])
        if st.get("data"):
            self._ask([0x1A, 0x06] + st["data"])


class YaesuCatPTT(_CatSerialPTT):
    """Yaesu text CAT: PTT (TX1; / TX0;), frequency (FA) and mode (MD) -
    FT-991A, FTDX10/101, FT-710 and other newer radios."""
    can_tune = True

    def __init__(self, port, baud=38400):
        super().__init__(port, baud)
        self.name = f"Yaesu CAT on {port}"

    def _cmd(self, on):
        return b"TX1;" if on else b"TX0;"

    def _ask(self, cmd, reply=False):
        self.ser.reset_input_buffer()
        self.ser.write(cmd.encode())
        self.ser.flush()
        if not reply:
            time.sleep(0.1)
            return ""
        data, t0 = b"", time.time()
        while time.time() - t0 < 0.6 and not data.endswith(b";"):
            data += self.ser.read(32)
        return data.decode(errors="replace").strip()

    def read_state(self):
        st = {}
        f = self._ask("FA;", True)
        if f.startswith("FA") and f[2:-1].isdigit():
            st["hz"] = int(f[2:-1])
        m = self._ask("MD0;", True)
        if m.startswith("MD0") and len(m) >= 5:
            st["mode"] = m[3]
        return st

    def tune(self, hz):
        self._ask(f"FA{int(hz):09d};")
        self._ask("MD0A;")                            # DATA-FM
        f = self._ask("FA;", True)
        if f and f.startswith("FA") and f[2:-1].isdigit() and int(f[2:-1]) != int(hz):
            raise IOError(f"radio is on {int(f[2:-1]) / 1e6:.4f} MHz, not {hz / 1e6:.4f} MHz")
        if not f:
            raise IOError("no reply from the radio (check CAT port and baud rate)")

    def restore(self, st):
        if st.get("hz"):
            self._ask(f"FA{int(st['hz']):09d};")
        if st.get("mode"):
            self._ask(f"MD0{st['mode']};")


def make_ptt(kind, port="", baud=9600, civ_addr="7C", line="RTS",
             invert=False, cm108_gpio=3, rigctld="127.0.0.1:4532"):
    """Build a PTT driver from a preset's fields. kind is one of:
    VOX, RTS, DTR, CM108, RIGCTLD, CIV, YAESU_CAT."""
    k = (kind or "VOX").upper()
    if k == "VOX":
        return PTT()
    if k in ("RTS", "DTR"):
        return SerialPTT(port, line=k, invert=invert)
    if k == "CM108":
        return CM108PTT(device=port or "/dev/hidraw0", gpio=cm108_gpio)
    if k == "RIGCTLD":
        host, _, p = (rigctld or "127.0.0.1:4532").partition(":")
        return RigctldPTT(host or "127.0.0.1", int(p or 4532))
    if k == "CIV":
        return CivPTT(port, baud=baud, addr=civ_addr)
    if k in ("YAESU_CAT", "YAESU"):
        return YaesuCatPTT(port, baud=baud)
    raise ValueError(f"unknown PTT kind: {kind}")


if __name__ == "__main__":
    # Dry self-test: build drivers and exercise the CI-V encoders (no hardware).
    assert hz_to_civ_bcd(144390000) == bytes([0x00, 0x00, 0x39, 0x44, 0x01]), "CI-V BCD"
    assert civ_bcd_to_hz(hz_to_civ_bcd(433500000)) == 433500000, "CI-V BCD round-trip"
    f = civ_ptt_command("7C", True)
    assert f[:4] == bytes([0xFE, 0xFE, 0x7C, 0xE0]) and f[-1] == 0xFD, "CI-V frame"
    for kind in ("VOX", "RTS", "DTR", "CM108", "RIGCTLD", "CIV", "YAESU_CAT"):
        d = make_ptt(kind, port="/dev/ttyUSB0", civ_addr="7C", baud=9600)
        print(f"  {kind:10s} -> {d.name:28s} can_tune={d.can_tune}")
    print("einstein_ptt self-test OK (encoders verified; drivers built without hardware)")
