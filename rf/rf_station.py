#!/usr/bin/env python3
"""
PigeonFSK station — Windows RF runner
=====================================
Runs on a Windows PC connected to a ham transceiver through a sound-card
interface (SignaLink / Digirig / rigblaster), exactly like the Tradewind/Lobster
setup. The phone can't key a radio, so the PC does the RF; the phone just shows
the map.

  TX:  beacon your callsign + Maidenhead grid on a schedule (clear text).
  RX:  listen, decode heard stations, print them as JSON, and (optionally) push
       them to the Pigeon relay so they appear on the Pigeon map as ham stations.

Audio uses `sounddevice` if installed (pip install sounddevice); otherwise it
falls back to reading/writing WAV files so you can test with any recorder.

LEGAL: amateur radio forbids encryption. PigeonFSK is clear text. Transmit only
on amateur bands you are licensed for, identify per your regulations, and respect
band plans. This tool does not key PTT by itself — use VOX or your interface's
PTT. Internet sharing in Pigeon stays AES-256 encrypted; that never touches RF.
"""

import sys, os, time, json, argparse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pigeon_rf as rf

# ---- Maidenhead grid -> lat/lon (square/subsquare centre) -----------------------
def grid_to_latlon(g):
    g = g.strip()
    if len(g) < 4: return None
    try:
        lon = (ord(g[0].upper()) - 65) * 20 - 180
        lat = (ord(g[1].upper()) - 65) * 10 - 90
        lon += int(g[2]) * 2
        lat += int(g[3]) * 1
        if len(g) >= 6:
            lon += (ord(g[4].upper()) - 65) * (2 / 24) + (1 / 24)
            lat += (ord(g[5].upper()) - 65) * (1 / 24) + (0.5 / 24)
        else:
            lon += 1; lat += 0.5
        return round(lat, 4), round(lon, 4)
    except Exception:
        return None

# ---- optional soundcard ---------------------------------------------------------
def have_sd():
    try:
        import sounddevice  # noqa
        return True
    except Exception:
        return False

def play(samples):
    import sounddevice as sd
    sd.play(samples.astype(np.float32), rf.FS); sd.wait()

def record(seconds):
    import sounddevice as sd
    n = int(seconds * rf.FS)
    a = sd.rec(n, samplerate=rf.FS, channels=1, dtype="float32"); sd.wait()
    return a.flatten().astype(np.float64)

# ---- push a heard station to the Pigeon relay (clear text) ----------------------
def push_relay(relay, st):
    try:
        body = json.dumps(st).encode()
        req = urllib.request.Request(relay.rstrip("/") + "/rf", data=body,
                                     headers={"content-type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=8).read()
        return True
    except Exception as e:
        print("  (relay push failed:", e, ")")
        return False

# ---- TX --------------------------------------------------------------------------
def tx(call, grid, interval, relay=None, once=False):
    print(f"TX PigeonFSK  {call} {grid}  every {interval}s  ({rf.NTONES}-FSK {rf.BAUD:.1f} Bd, clear text)")
    while True:
        sig = rf.modulate(call, grid, 0x2F)
        if have_sd():
            print(f"  keying tone... {len(sig)/rf.FS:.1f}s  (use VOX/PTT)"); play(sig)
        else:
            rf.transmit(call, grid, path="pigeon_tx.wav")
            print("  wrote pigeon_tx.wav (no soundcard lib) — play it into your rig")
        if relay:
            ll = grid_to_latlon(grid)
            if ll: push_relay(relay, {"callsign": call, "grid": grid, "lat": ll[0], "lon": ll[1],
                                      "ts": int(time.time()*1000), "mode": "PigeonFSK"})
        if once: break
        time.sleep(interval)

# ---- RX --------------------------------------------------------------------------
def rx(relay=None, wav=None, chunk=12.0):
    if wav:
        r = rf.receive(wav)
        print(json.dumps(r));
        if r and relay:
            ll = grid_to_latlon(r["grid"])
            if ll: push_relay(relay, {**r, "lat": ll[0], "lon": ll[1], "ts": int(time.time()*1000), "mode": "PigeonFSK"})
        return
    if not have_sd():
        print("RX needs `pip install sounddevice`, or pass --wav FILE to decode a recording."); return
    print(f"RX listening ({chunk:.0f}s windows). Ctrl-C to stop.")
    heard = {}
    while True:
        audio = record(chunk)
        r = rf.demodulate(audio)
        if r:
            ll = grid_to_latlon(r["grid"]) or (None, None)
            st = {**r, "lat": ll[0], "lon": ll[1], "ts": int(time.time()*1000), "mode": "PigeonFSK"}
            key = r["callsign"]
            if key not in heard or time.time() - heard[key] > 5:
                print("HEARD", json.dumps(st))
                heard[key] = time.time()
                if relay and ll[0] is not None: push_relay(relay, st)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="PigeonFSK ham RF station (Windows + radio + soundcard)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tx"); t.add_argument("callsign"); t.add_argument("grid")
    t.add_argument("--interval", type=int, default=600); t.add_argument("--relay", default=None); t.add_argument("--once", action="store_true")
    r = sub.add_parser("rx"); r.add_argument("--relay", default=None); r.add_argument("--wav", default=None); r.add_argument("--chunk", type=float, default=12.0)
    a = ap.parse_args()
    if a.cmd == "tx": tx(a.callsign, a.grid, a.interval, a.relay, a.once)
    else: rx(a.relay, a.wav, a.chunk)
