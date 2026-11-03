#!/usr/bin/env python3
"""
Pigeon RF station — TX & RX, all modes, HF + VHF
================================================
Runs on a PC connected to a ham transceiver through a sound-card interface
(SignaLink / Digirig / rigblaster). The PC does the RF; the phone shows the map.
Works on any band the rig covers (HF SSB and VHF/UHF SSB) — the waveform is audio
into SSB, so the band is just where you tune the radio.

MODES (pick with --mode):
  fsk1   PigeonFSK-1   — 16-FSK + Hamming, ~-8 dB, short beacon (robust, quick)
  homer  HOMER (AVIAN) — 16-FSK + soft-Viterbi conv FEC, ~-21 dB, 31 s (weak-signal)

COMMANDS:
  tx     beacon callsign + grid on a schedule (clear text)
  rx     listen, decode heard stations, push to the Pigeon relay / map
  ale    Barrett-4050-style link layer: sound (beacon), scan, or call a station
         by Selcal address over the best channel (see pigeon_ale.py)

LEGAL: amateur radio forbids ENCRYPTION — everything here is CLEAR TEXT. Transmit
only on bands you are licensed for, identify per your regulations, respect band
plans. This tool does not key PTT by itself; use VOX or your interface's PTT.
Pigeon's internet sharing stays AES-256 — that never touches RF.
"""
import sys, os, time, json, argparse, urllib.request, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pigeon_rf, pigeon_rf2, pigeon_ale

CODECS = {"fsk1": pigeon_rf, "homer": pigeon_rf2}
FS = 12000

def grid_to_latlon(g):
    g = (g or "").strip()
    if len(g) < 4: return None
    try:
        lon = (ord(g[0].upper())-65)*20-180; lat = (ord(g[1].upper())-65)*10-90
        lon += int(g[2])*2; lat += int(g[3])*1
        if len(g) >= 6:
            lon += (ord(g[4].upper())-65)*(2/24)+(1/24); lat += (ord(g[5].upper())-65)*(1/24)+(0.5/24)
        else: lon += 1; lat += 0.5
        return round(lat,4), round(lon,4)
    except Exception: return None

def have_sd():
    try: import sounddevice; return True
    except Exception: return False
def play(samples):
    import sounddevice as sd; sd.play(samples.astype(np.float32), FS); sd.wait()
def record(seconds):
    import sounddevice as sd
    a = sd.rec(int(seconds*FS), samplerate=FS, channels=1, dtype="float32"); sd.wait()
    return a.flatten().astype(np.float64)
def write_wav(path, samples):
    pcm = (np.clip(samples,-1,1)*32767).astype("<i2")
    with wave.open(path,"wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(FS); w.writeframes(pcm.tobytes())
def read_wav(path):
    with wave.open(path,"rb") as w: raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, "<i2").astype(np.float64)/32768.0

def push_relay(relay, st):
    try:
        req = urllib.request.Request(relay.rstrip("/")+"/rf", data=json.dumps(st).encode(),
                                     headers={"content-type":"application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=8).read(); return True
    except Exception as e:
        print("  (relay push failed:", e, ")"); return False

def tx(mode, call, grid, interval, relay=None, once=False):
    rf = CODECS[mode]
    print(f"TX {mode.upper()}  {call} {grid}  every {interval}s  (clear text, HF/VHF SSB)")
    while True:
        sig = rf.modulate(call, grid, 0x2F)
        if have_sd(): print(f"  keying {len(sig)/FS:.1f}s (VOX/PTT)…"); play(sig)
        else: write_wav("pigeon_tx.wav", sig); print("  wrote pigeon_tx.wav — play it into your rig")
        if relay:
            ll = grid_to_latlon(grid)
            if ll: push_relay(relay, {"callsign":call,"grid":grid,"lat":ll[0],"lon":ll[1],
                                      "ts":int(time.time()*1000),"mode":mode.upper()})
        if once: break
        time.sleep(interval)

def rx(mode, relay=None, wav=None, chunk=None):
    rf = CODECS[mode]; chunk = chunk or (14.0 if mode=="fsk1" else 36.0)
    if wav:
        r = rf.demodulate(read_wav(wav)); print(json.dumps(r))
        if r and relay:
            ll = grid_to_latlon(r.get("grid"))
            if ll: push_relay(relay, {**r,"lat":ll[0],"lon":ll[1],"ts":int(time.time()*1000),"mode":mode.upper()})
        return
    if not have_sd(): print("RX needs `pip install sounddevice`, or pass --wav FILE."); return
    print(f"RX {mode.upper()} listening ({chunk:.0f}s windows). Ctrl-C to stop.")
    heard = {}
    while True:
        r = rf.demodulate(record(chunk))
        if r:
            ll = grid_to_latlon(r.get("grid")) or (None,None)
            st = {**r,"lat":ll[0],"lon":ll[1],"ts":int(time.time()*1000),"mode":mode.upper()}
            k = r["callsign"]
            if k not in heard or time.time()-heard[k] > 5:
                print("HEARD", json.dumps(st)); heard[k]=time.time()
                if relay and ll[0] is not None: push_relay(relay, st)

# ---- ALE: Barrett-4050-style sound / scan / call over soundcard ----------------
def ale(addr, channels, action, dst=None, dwell=3.0):
    def send(ch, samples):
        print(f"  TX on ch{ch} ({channels[ch]}) — tune the rig there, then key (VOX/PTT)")
        if have_sd(): play(samples)
        else: write_wav(f"ale_tx_ch{ch}.wav", samples)
    def recv(ch, secs):
        print(f"  RX on ch{ch} ({channels[ch]}) for {secs:.0f}s — tune the rig there")
        return record(secs) if have_sd() else None
    st = pigeon_ale.Station(addr, channels, send=send, recv=recv)
    if action == "sound": st.sound(); print("Sounded on all channels.")
    elif action == "scan": st.scan(dwell); print("LQA:", {f"{p}@{c}":round(float(v),1) for (p,c),v in st.lqa.items()})
    elif action == "call":
        if not dst: print("call needs --dst ADDRESS"); return
        print("ALE call result:", st.call(dst))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Pigeon RF station — TX/RX all modes, HF+VHF, + ALE")
    ap.add_argument("--mode", choices=list(CODECS), default="homer", help="fsk1 (quick) or homer (weak-signal)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tx"); t.add_argument("callsign"); t.add_argument("grid")
    t.add_argument("--interval", type=int, default=600); t.add_argument("--relay"); t.add_argument("--once", action="store_true")
    r = sub.add_parser("rx"); r.add_argument("--relay"); r.add_argument("--wav"); r.add_argument("--chunk", type=float)
    a_ = sub.add_parser("ale"); a_.add_argument("action", choices=["sound","scan","call"])
    a_.add_argument("--addr", required=True); a_.add_argument("--channels", required=True, help="comma list, e.g. 14.1086,18.1060,144.174")
    a_.add_argument("--dst"); a_.add_argument("--dwell", type=float, default=3.0)
    a = ap.parse_args()
    if a.cmd == "tx": tx(a.mode, a.callsign, a.grid, a.interval, a.relay, a.once)
    elif a.cmd == "rx": rx(a.mode, a.relay, a.wav, a.chunk)
    else: ale(a.addr, a.channels.split(","), a.action, a.dst, a.dwell)
