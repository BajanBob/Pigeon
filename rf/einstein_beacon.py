#!/usr/bin/env python3
"""
Einstein Beacon & Chat — hailing, capability negotiation, live chat  (Claude)
=============================================================================
Clear-text (amateur-legal) VHF/HF digital hailing and a negotiated live chat over
the Einstein modem.

  * EINSTEIN BEACON : a named sounding/hailing frame carrying callsign + grid +
    capability flags (which modem profiles the station supports) + SNR it heard you at.
    Sent as a CQ (hailing anyone) or addressed to a specific callsign.
  * NEGOTIATION     : on hearing a hail, the two stations pick the FASTEST modem
    profile they BOTH support that the measured SNR can carry (cognitive link adapt).
  * CHAT            : bidirectional text frames over the agreed profile; speed is
    renegotiated on the fly if the link changes.

All clear text. Beacon/chat frames are compressed (zlib, reversible — not a cipher).
NOT interoperable with other beacon systems; Einstein-native.
"""
import zlib, struct, time, json
import einstein_modem as em
from einstein_cognitive import adapt_link, band_of

BMAGIC = b"EB1"                       # Einstein Beacon v1
# capability bit flags
CAP = {"STANDARD": 1, "PRO": 2, "PRO_VHF": 4}
def caps_to_mask(profiles):
    m = 0
    for p in profiles: m |= CAP.get(p, 0)
    return m
def mask_to_caps(m): return [p for p, b in CAP.items() if m & b]

# ---------- beacon frame ----------
def build_beacon(callsign, grid, freq_mhz, profiles, target="CQ", heard_snr=None):
    payload = json.dumps(dict(c=callsign.upper(), g=grid.upper(), f=round(freq_mhz,4),
                              cap=caps_to_mask(profiles), tgt=target.upper(),
                              snr=(None if heard_snr is None else round(heard_snr,1)),
                              t=int(time.time()))).encode()
    comp = zlib.compress(payload, 9)
    return BMAGIC + struct.pack(">H", len(comp)) + comp

def parse_beacon(frame):
    if frame[:3] != BMAGIC: raise ValueError("not an Einstein Beacon")
    n = struct.unpack(">H", frame[3:5])[0]
    d = json.loads(zlib.decompress(frame[5:5+n]))
    d["caps"] = mask_to_caps(d["cap"])
    return d

# ---------- negotiation ----------
def negotiate(my_caps, their_caps, snr_db, band):
    """Pick the fastest profile both support that the SNR can carry."""
    common = [p for p in ["PRO_VHF","PRO","STANDARD"] if p in my_caps and p in their_caps]
    if not common:
        return dict(ok=False, reason="no common profile", profile=None)
    snr_choice = adapt_link(snr_db, band)["profile"]          # what the SNR allows
    order = ["STANDARD","PRO","PRO_VHF"]
    cap = order.index(snr_choice)
    pick = None
    for p in common:                                          # common is fastest-first
        if order.index(p) <= cap: pick = p; break
    if pick is None: pick = "STANDARD" if "STANDARD" in common else common[-1]
    return dict(ok=True, profile=pick, snr_db=snr_db, band=band,
                reason=f"both support {common}; SNR {snr_db} dB on {band} allows up to {snr_choice} -> {pick}")

# ---------- chat over the agreed profile ----------
def send_chat(text, profile, channel=None):
    blob = b"ECHAT" + zlib.compress(text.encode(), 9)
    y, meta = em.modulate(blob, profile)
    r = channel(y) if channel else y
    got = em.demodulate(r, profile, meta)
    if got is None or got[:5] != b"ECHAT": return None
    return zlib.decompress(got[5:]).decode("utf-8", "replace")

# ---------- demo: two stations hail, negotiate, chat ----------
if __name__ == "__main__":
    print("Einstein Beacon & Chat self-test\n")
    # Station A (me) hails CQ on 2m with full capability
    a_caps = ["STANDARD","PRO","PRO_VHF"]; b_caps = ["STANDARD","PRO"]   # B is HF-only radio
    hail = build_beacon("8P6NH","GK03",144.3,a_caps,target="CQ")
    print(f"A hails: {len(hail)} byte Einstein Beacon (CQ on 144.3)")
    d = parse_beacon(hail)
    print(f"B decodes beacon: {d['c']} @ {d['g']} caps={d['caps']} target={d['tgt']}")

    # B answers, A hears B at +28 dB on 2m FM -> negotiate
    for snr, band in [(28,"2m"), (12,"HF"), (4,"HF")]:
        n = negotiate(a_caps, b_caps, snr, band)
        print(f"  negotiate @ {snr:+3d} dB {band}: -> {n['profile']:9} [{n['reason']}]")

    # live chat on the 2m negotiation (PRO since B lacks PRO_VHF)
    prof = negotiate(a_caps, b_caps, 28, "2m")["profile"]
    print(f"\nLive chat using {prof}:")
    for msg in ["8P6NH de VP8XYZ gm, 59 here", "VP8XYZ de 8P6NH tnx, Einstein chat FB!"]:
        rx = send_chat(msg, prof)
        print(f"  TX: {msg!r}\n  RX: {rx!r}  {'OK' if rx==msg else 'FAIL'}")
