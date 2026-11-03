#!/usr/bin/env python3
# Einstein — standalone desktop station runner.
# Ties the audio engine + a radio preset + PTT/CAT + the codecs together so
# Einstein operates on its own on a PC/Pi: capture rig audio for analysis
# (SSP/drift), key PTT, tune by CAT, and TX/RX the AFSK / Robust / OFDM
# modems — no external helper required.
#
# All on-air content is CLEAR TEXT. zlib compression (reversible, key-less)
# is fine; no encryption is ever applied to RF.
"""
Usage:
  einstein_station.py --radios                 list radio presets
  einstein_station.py --devices                list audio devices
  einstein_station.py --radio ic9100 --info    show resolved settings
  einstein_station.py --radio ic9100 --analyze 3
                                               capture 3s rig audio -> analysis
                                               (feeds SSP / drift discriminator)
  einstein_station.py --radio ft991a --tune 144390000
                                               set frequency via CAT (if supported)
  einstein_station.py --radio ic9100 --tx-test "DE 8P5AB TEST" [--modem afsk1200]
                                               key PTT and send one clear-text frame
  einstein_station.py --radio ic9100 --rx [--modem afsk1200] [--secs 30]
                                               listen and decode frames

Modems: afsk1200 (VHF FM), afsk300 (HF SSB), robust (weak-signal HF 8-FSK),
        ofdm-std / ofdm-pro / ofdm-prov (Einstein Modem).
"""

import sys
import time

sys.path.insert(0, ".")
import einstein_radios as RADIOS           # noqa: E402
import einstein_ptt as PTT                  # noqa: E402

RATE_DEFAULT = 48000


def _afsk():
    import einstein_afsk as afsk
    return afsk


def _resolve(radio_id):
    cfg = RADIOS.get(radio_id)
    cat = RADIOS.cat_params(radio_id)
    return cfg, cat


def cmd_radios():
    for r in RADIOS.RADIOS:
        c = RADIOS.get(r["id"])
        civ = f"CI-V {c['civ_addr']}" if c["ptt"] == "CIV" else c["ptt"]
        print(f"  {c['id']:14s} {civ:14s} {c.get('bands',''):8s} {c['label']}")


def cmd_devices():
    import einstein_audio as A
    devs, err = A.list_devices()
    if err:
        print(err); return 1
    for d in devs:
        print(f"  [{d['index']:2d}] in={d['inputs']} out={d['outputs']}  {d['name']}")
    return 0


def cmd_info(radio_id, port):
    cfg, cat = _resolve(radio_id)
    print(f"Radio      : {cfg['label']}")
    print(f"Bands      : {cfg.get('bands','?')}")
    print(f"Audio dev  : {cfg.get('audio','(default)')}  @ {cfg.get('sample_rate',RATE_DEFAULT)} Hz")
    print(f"PTT        : {cfg['ptt']}"
          + (f"  CI-V {cfg['civ_addr']} @ {cfg['cat_baud']} baud" if cfg['ptt'] == 'CIV' else "")
          + (f"  CAT @ {cfg['cat_baud']} baud" if cfg['ptt'] == 'YAESU_CAT' else "")
          + (f"  {cfg.get('ptt_port','')}" if cfg['ptt'] == 'RIGCTLD' else ""))
    print(f"Rec. modem : {cfg.get('modem','?')}")
    drv = PTT.make_ptt(port=port, **cat)
    print(f"PTT driver : {drv.name}  (can_tune={drv.can_tune})")
    print(f"Note       : {cfg.get('note','')}")
    return 0


def cmd_analyze(radio_id, secs, in_dev, rate):
    import einstein_audio as A
    pipe = A.AudioPipe(radio_id, in_dev=in_dev, rate=rate)
    print(f"Capturing {secs}s from {pipe.in_dev or 'default device'} @ {pipe.rate} Hz …")
    res = pipe.analyze(secs)
    import json
    print(json.dumps(res, indent=2))
    print("\n(These numbers feed the analyzer, SSP and the drift / sea-Doppler "
          "discriminator — the rig-audio pipe Einstein previously lacked.)")
    return 0


def cmd_tune(radio_id, hz, port):
    cfg, cat = _resolve(radio_id)
    drv = PTT.make_ptt(port=port, **cat)
    if not getattr(drv, "can_tune", False):
        print(f"{cfg['label']} PTT method '{cfg['ptt']}' can't tune by CAT — set the radio by hand.")
        return 1
    drv.open()
    try:
        drv.tune(int(hz))
        print(f"Tuned to {int(hz)/1e6:.4f} MHz (FM data mode where supported).")
    finally:
        drv.close()
    return 0


def _modulate(modem, text, rate):
    data = text.encode("latin-1", "replace")
    m = (modem or "afsk1200").lower()
    if m in ("afsk1200", "1200"):
        afsk = _afsk()
        frame = afsk.encode_ax25("EINSTEIN", "CQ", [], text)
        return afsk.modulate(frame, rate=rate, modem="1200")
    if m in ("afsk300", "300"):
        afsk = _afsk()
        frame = afsk.encode_ax25("EINSTEIN", "CQ", [], text)
        return afsk.modulate(frame, rate=rate, modem="300")
    if m == "robust":
        afsk = _afsk()
        return afsk.robust_modulate(data, rate=rate)
    if m.startswith("ofdm"):
        import einstein_modem as EM
        prof = {"ofdm-std": "STANDARD", "ofdm-pro": "PRO", "ofdm-prov": "PRO_VHF"}[m]
        P = EM.PROFILES[prof]
        return EM.modulate(data, P)
    raise ValueError(f"unknown modem: {modem}")


def cmd_tx_test(radio_id, text, modem, port, out_dev, rate):
    import einstein_audio as A
    cfg, cat = _resolve(radio_id)
    audio = _modulate(modem, text, rate)
    secs = len(audio) / rate
    drv = PTT.make_ptt(port=port, **cat)
    print(f"TX {cfg['label']}: '{text}'  modem={modem or 'afsk1200'}  ({secs:.1f}s, clear text)")
    drv.open()
    try:
        drv.key(True)
        time.sleep(0.2)                       # TX settle
        A.play(audio, device=out_dev or cfg.get("audio"), rate=rate)
    finally:
        drv.key(False)
        drv.close()
    print("TX complete, PTT released.")
    return 0


def cmd_rx(radio_id, modem, secs, in_dev, rate):
    import einstein_audio as A
    cfg, _ = _resolve(radio_id)
    m = (modem or "afsk1200").lower()
    afsk = _afsk()
    if m in ("afsk1200", "1200"):
        dem = afsk.Demodulator(rate, "1200"); robust = False
    elif m in ("afsk300", "300"):
        dem = afsk.Demodulator(rate, "300"); robust = False
    elif m == "robust":
        dem = afsk.RobustDemodulator(rate); robust = True
    else:
        print("RX supports afsk1200 / afsk300 / robust in this build."); return 1
    print(f"RX {cfg['label']} for {secs}s, modem={m} …  (Ctrl-C to stop)")
    t0 = time.time()
    try:
        for block in A.stream_blocks(device=in_dev or cfg.get("audio"), rate=rate):
            for fr in dem.process(block):
                if robust:
                    print("  decoded:", fr.decode("latin-1", "replace"))
                else:
                    line = afsk.decode_ax25(fr)
                    if line:
                        print("  decoded:", line)
            if time.time() - t0 > secs:
                break
    except KeyboardInterrupt:
        pass
    print("RX stopped.")
    return 0


def main(argv):
    def opt(name, default=None, cast=str):
        return cast(argv[argv.index(name) + 1]) if name in argv else default
    port = opt("--port", "")
    rate = opt("--rate", RATE_DEFAULT, int)
    radio = opt("--radio")
    modem = opt("--modem")
    in_dev = opt("--in")
    out_dev = opt("--out")

    if "--radios" in argv:
        return cmd_radios()
    if "--devices" in argv:
        return cmd_devices()
    if radio and "--info" in argv:
        return cmd_info(radio, port)
    if radio and "--analyze" in argv:
        return cmd_analyze(radio, opt("--analyze", 3.0, float), in_dev, rate)
    if radio and "--tune" in argv:
        return cmd_tune(radio, opt("--tune", 0, int), port)
    if radio and "--tx-test" in argv:
        return cmd_tx_test(radio, opt("--tx-test", "DE 8P5AB TEST"), modem, port, out_dev, rate)
    if radio and "--rx" in argv:
        return cmd_rx(radio, modem, opt("--secs", 30, float), in_dev, rate)
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
