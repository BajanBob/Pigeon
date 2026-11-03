#!/usr/bin/env python3
"""
Einstein Cognitive Engine — AI-driven link & propagation decisions (Claude)
===========================================================================
A transparent cognitive-radio controller for the Einstein station. It ingests what
the station actually hears — heard-station spots and sounding-beacon reports — and
decides, with reasons you can read:

  * PROPAGATION CLASSIFICATION  : F2 / Sporadic-E / Tropo-duct / TEP / Tropo-scatter /
                                  Meteor-scatter / Ground-wave, per heard station,
                                  with a confidence and the evidence used.
  * PROPAGATION DIRECTIONS      : which azimuth sectors are open, to where, and how.
  * LINK ADAPTATION             : pick modem profile + FEC strength + speed from the
                                  measured SNR / link-quality, throttling up or down.
  * REDUNDANCY / FAILOVER       : when a link degrades, fall back to a more robust
                                  profile, an alternate band, or beacon re-hail.

This is a HEURISTIC, EXPLAINABLE engine (rules grounded in propagation physics), not a
black box and not a guarantee. Every decision carries the facts it was based on so an
operator can audit it. "AI-driven" here means it senses its operational theatre and
adapts autonomously — honestly, within what the physics and the data support.
"""
import math, time, json
from dataclasses import dataclass, field, asdict

# reuse geometry from the SSP module
from ssp_predict import grid_to_latlon, gc_distance_bearing

# ---------- inputs ----------
@dataclass
class Spot:
    """A heard station or heard beacon."""
    callsign: str
    grid: str
    freq_mhz: float
    snr_db: float
    ts: float = field(default_factory=lambda: time.time())
    is_beacon: bool = False          # True if from a sounding/Einstein beacon
    mode: str = ""                   # optional reported mode

# ---------- band / geometry helpers ----------
def band_of(freq_mhz):
    if freq_mhz < 30:   return "HF"
    if freq_mhz < 54:   return "6m"
    if freq_mhz < 148:  return "2m"
    if freq_mhz < 450:  return "70cm"
    return "UHF+"

def crosses_equator(la1, la2):
    return (la1 > 0) != (la2 > 0)

def is_north_south(brg):
    # within 45° of due N or due S
    d = min(abs(brg-0), abs(brg-180), abs(brg-360))
    return d <= 45

# ---------- propagation classifier (explainable) ----------
def classify_path(spot, my_grid, now=None):
    now = now or time.time()
    la1, lo1 = grid_to_latlon(my_grid); la2, lo2 = grid_to_latlon(spot.grid)
    dist, brg = gc_distance_bearing(la1, lo1, la2, lo2)
    band = band_of(spot.freq_mhz); hour = time.gmtime(now).tm_hour
    midlat = (abs(la1)+abs(la2))/2
    cands = []   # (mode, confidence, reason)

    if band == "HF":
        if dist > 2500:
            cands.append(("F2", 0.8, f"HF, {dist:.0f} km > 2500 km — classic F2 skip"))
        elif dist > 400:
            cands.append(("F2/NVIS", 0.5, f"HF, {dist:.0f} km — F2/E one-hop or NVIS"))
        else:
            cands.append(("Ground-wave/NVIS", 0.6, f"HF, short {dist:.0f} km"))
        if crosses_equator(la1, la2) and is_north_south(brg) and dist > 3000 and 14 <= hour <= 23:
            cands.append(("TEP", 0.6, "HF path crosses the geomagnetic equator, N–S, afternoon/evening"))
    elif band in ("6m", "2m"):
        if 800 <= dist <= 2300 and band == "6m":
            cands.append(("Sporadic-E", 0.75, f"6m, {dist:.0f} km in the 800–2300 km single-hop Es window"))
        if band == "6m" and 2300 < dist <= 9000:
            cands.append(("Multi-hop Es / F2", 0.45, f"6m, {dist:.0f} km — multi-hop Es or F2 (solar-dependent)"))
        if band == "2m" and 1000 <= dist <= 2200:
            cands.append(("Sporadic-E", 0.45, f"2m, {dist:.0f} km — rarer 2m Es, possible"))
        if crosses_equator(la1, la2) and is_north_south(brg) and 3000 <= dist <= 8000 and 15 <= hour <= 23 and midlat < 35:
            cands.append(("TEP", 0.7, f"VHF, N–S trans-equatorial geometry, {dist:.0f} km, evening, low mid-latitude"))
        if dist <= 2000 and spot.snr_db > -5:
            cands.append(("Tropo-duct", 0.55, f"VHF, {dist:.0f} km, workable SNR — tropospheric ducting"))
        if dist <= 300:
            cands.append(("Ground-wave/LOS", 0.7, f"VHF short {dist:.0f} km — line-of-sight / ground wave"))
        if 300 < dist <= 2000:
            cands.append(("Tropo-scatter", 0.3, f"VHF {dist:.0f} km — weak forward tropo-scatter always possible"))
        if 400 <= dist <= 2300 and spot.is_beacon is False:
            cands.append(("Meteor-scatter", 0.2, f"VHF {dist:.0f} km — meteor-scatter bursts possible"))
    elif band == "70cm":
        if dist <= 300:
            cands.append(("Ground-wave/LOS", 0.7, f"70cm short {dist:.0f} km"))
        if dist <= 1500 and spot.snr_db > -3:
            cands.append(("Tropo-duct", 0.6, f"70cm, {dist:.0f} km — ducting (70cm ducts well over sea)"))
        if 300 < dist <= 1500:
            cands.append(("Tropo-scatter", 0.3, f"70cm {dist:.0f} km — tropo-scatter"))

    if not cands:
        if band in ("2m","70cm") and dist > 2300:
            cands.append(("Beyond normal VHF/UHF modes", 0.15,
                          f"{band}, {dist:.0f} km — past normal tropo/Es/TEP reach; only exceptional chains"))
        else:
            cands.append(("Unknown", 0.2, f"{band}, {dist:.0f} km — no strong match"))
    cands.sort(key=lambda c: -c[1])
    best = cands[0]
    return dict(callsign=spot.callsign, grid=spot.grid, band=band, freq_mhz=spot.freq_mhz,
                distance_km=round(dist, 1), distance_mi=round(dist/1.609, 1), bearing_deg=round(brg, 1),
                snr_db=spot.snr_db, mode=best[0], confidence=round(best[1], 2), reason=best[2],
                alternatives=[{"mode": m, "confidence": round(c, 2), "reason": r} for m, c, r in cands[1:]])

# ---------- direction analysis ----------
def direction_analysis(spots, my_grid, now=None):
    sectors = {}   # 8-point compass -> list of classifications
    names = ["N","NE","E","SE","S","SW","W","NW"]
    for sp in spots:
        c = classify_path(sp, my_grid, now)
        idx = int(((c["bearing_deg"]+22.5) % 360)//45); sec = names[idx]
        sectors.setdefault(sec, []).append(c)
    out = []
    for sec in names:
        lst = sectors.get(sec, [])
        if not lst: continue
        modes = {}
        for c in lst: modes[c["mode"]] = max(modes.get(c["mode"], 0), c["confidence"])
        best_mode = max(modes, key=modes.get)
        out.append(dict(sector=sec, stations=len(lst), dominant_mode=best_mode,
                        confidence=round(modes[best_mode], 2),
                        max_km=round(max(c["distance_km"] for c in lst), 0),
                        calls=[c["callsign"] for c in lst]))
    return out

# ---------- link adaptation (throttle up/down) ----------
# ordered weakest->fastest; each needs a minimum SNR (from the modem FER measurements)
LINK_LADDER = [
    dict(profile="STANDARD", fec="r1/2", min_snr=2,  bps=560,   note="most robust, airtime-governed"),
    dict(profile="PRO",      fec="r1/2", min_snr=10, bps=2679,  note="HF 16-QAM"),
    dict(profile="PRO_VHF",  fec="r1/2", min_snr=25, bps=9000,  note="VHF/FM 64-QAM, needs strong link"),
]
def adapt_link(snr_db, band="HF", margin_db=3.0):
    """Pick the fastest rung whose min_snr fits (snr minus a safety margin)."""
    usable = snr_db - margin_db
    # PRO_VHF only on VHF/UHF FM
    ladder = [r for r in LINK_LADDER if not (r["profile"]=="PRO_VHF" and band in ("HF","6m"))]
    choice = ladder[0]
    for r in ladder:
        if usable >= r["min_snr"]: choice = r
    idx = LINK_LADDER.index(choice)
    return dict(**choice, decision="throttle to "+choice["profile"],
                headroom_db=round(usable-choice["min_snr"], 1),
                can_go_faster=idx < len(LINK_LADDER)-1 and not (band in ("HF","6m") and idx==1))

def redundancy_decision(link_history):
    """link_history: list of recent SNRs. Decide failover when trend degrades."""
    if len(link_history) < 3: return dict(action="hold", reason="not enough samples")
    recent = link_history[-3:]; trend = recent[-1]-recent[0]
    if recent[-1] < 0:
        return dict(action="failover", to="STANDARD + re-beacon",
                    reason=f"SNR {recent[-1]:.0f} dB below floor — drop to most robust profile and re-hail")
    if trend < -6:
        return dict(action="throttle_down", reason=f"SNR falling fast ({trend:.0f} dB over 3 samples) — step down a rung")
    if trend > 6:
        return dict(action="throttle_up", reason=f"SNR rising ({trend:+.0f} dB) — try the next faster rung")
    return dict(action="hold", reason=f"link stable (SNR {recent[-1]:.0f} dB)")

# ---------- demo ----------
if __name__ == "__main__":
    me = "GK03"   # Barbados-ish
    # fixed evening-UTC timestamp so time-gated modes (TEP) demonstrate
    import calendar
    EVE = calendar.timegm((2026,11,3,20,0,0,0,0,0))   # 20:00 UTC
    print("Einstein Cognitive Engine self-test (my grid", me, ", 20:00 UTC)\n")
    spots = [
        Spot("LU5DX", "GF05", 50.130, -8, is_beacon=True),    # S, trans-equatorial, 6m
        Spot("EA8ABC","IL38", 144.300, 3, is_beacon=True),    # NE, VHF long over sea
        Spot("W1AW",  "FN31", 14.074, 12),                    # N, HF
        Spot("PY2XYZ","GG66", 144.300, -2),                   # S, VHF TEP candidate
        Spot("8P9AB", "GK03", 432.100, 15),                   # local 70cm
    ]
    print("— Per-station classification —")
    for sp in spots:
        c = classify_path(sp, me, EVE)
        print(f"  {c['callsign']:6} {c['band']:4} {c['distance_km']:7.0f} km brg {c['bearing_deg']:5.0f}° "
              f"SNR {c['snr_db']:+3.0f} -> {c['mode']:16} (conf {c['confidence']})  [{c['reason']}]")
    print("\n— Direction analysis (open sectors) —")
    for d in direction_analysis(spots, me, EVE):
        print(f"  {d['sector']:2}: {d['dominant_mode']:16} to {d['max_km']:.0f} km "
              f"({d['stations']} stn, conf {d['confidence']}) {d['calls']}")
    print("\n— Link adaptation —")
    for snr, band in [(3,"HF"),(12,"HF"),(28,"2m"),(-1,"HF")]:
        a = adapt_link(snr, band)
        print(f"  SNR {snr:+3d} dB on {band:3} -> {a['profile']:9} {a['fec']} ({a['bps']} bps) "
              f"headroom {a['headroom_db']:+.0f} dB  [{a['note']}]")
    print("\n— Redundancy / failover —")
    for hist in [[18,16,15],[18,12,4],[2,-1,-3],[8,12,18]]:
        r = redundancy_decision(hist); print(f"  SNR {hist} -> {r['action'].upper():12} ({r['reason']})")
