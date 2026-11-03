#!/usr/bin/env python3
"""
International ALE channel plans  (AI-assisted, Claude)
=====================================================
Standard calling frequencies used for Automatic Link Establishment. All USB dial
frequencies in kHz. Transmit only on bands/segments you are licensed for and that
are permitted for ALE/data in your region — ALE channel plans are region-dependent.

HAM_HFN: the amateur "Global ALE High Frequency Network" (HFLINK) channel set, the
de-facto international ham ALE calling channels. VHF entries are common simplex
data frequencies (regional — verify your band plan).
"""
# amateur ALE (HFLINK HFN) — international calling channels, USB dial kHz
HAM_HFN = {
 "160m": [1996.0],
 "80m":  [3596.0],
 "60m":  [5357.0],                 # region-dependent (WRC-15 60 m band)
 "40m":  [7102.0, 7185.5],
 "30m":  [10145.5],
 "20m":  [14109.0],
 "17m":  [18106.0],
 "15m":  [21096.0],
 "12m":  [24926.0],
 "10m":  [28146.0],
 "6m":   [50140.0],
 "2m":   [144140.0],               # common weak-signal/data simplex (verify band plan)
 "70cm": [432140.0],
}

# A compact default scan group for a tropical/Atlantic station (edit for your QTH)
DEFAULT_SCAN = [3596.0, 7102.0, 10145.5, 14109.0, 18106.0, 21096.0, 28146.0]

def all_channels():
    out = []
    for band, chs in HAM_HFN.items():
        for f in chs: out.append((band, f))
    return out

def mhz(khz): return round(khz/1000.0, 4)

if __name__ == "__main__":
    print("Amateur ALE (HFLINK HFN) international calling channels (USB, kHz):\n")
    for band, chs in HAM_HFN.items():
        print(f"  {band:>5}: " + ", ".join(f"{f:.1f}" for f in chs))
    print("\nDefault HF scan group (MHz):", [mhz(f) for f in DEFAULT_SCAN])
