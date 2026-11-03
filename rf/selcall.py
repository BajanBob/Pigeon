#!/usr/bin/env python3
"""
Selcall tone systems — encode / decode  (AI-assisted, Claude)
=============================================================
Two-tone-sequential and dual-tone selective calling, as used by HF/VHF data
terminals (Codan, Barrett, marine/commercial) and aviation. Clear-text signalling.

Systems included (standard tone tables + timings):
  CCIR     numeric selcall, 100 ms tones (CCIR 1 set)
  ZVEI1    numeric selcall, 70 ms tones (European commercial)
  EEA      numeric selcall, 40 ms tones (CCIR frequency set, fast)
  SELCAL   aeronautical (ARINC 596/714): 4 letters as two DUAL-tone pairs, ~1 s each

Sequential systems use a REPEAT tone when two adjacent digits are equal (standard
behaviour) so the decoder can tell them apart.
"""
import numpy as np

FS = 8000
# ---- numeric sequential tone sets (Hz). 'R' = repeat/again tone ----
SETS = {
 "CCIR":  {"freqs":{"0":1981,"1":1124,"2":1197,"3":1275,"4":1358,"5":1446,"6":1540,"7":1640,
                    "8":1747,"9":1860,"R":2400,"GROUP":2247}, "dur":0.100},
 "ZVEI1": {"freqs":{"0":2400,"1":1060,"2":1160,"3":1270,"4":1400,"5":1530,"6":1670,"7":1830,
                    "8":2000,"9":2200,"R":2600,"GROUP":2800}, "dur":0.070},
 "EEA":   {"freqs":{"0":1981,"1":1124,"2":1197,"3":1275,"4":1358,"5":1446,"6":1540,"7":1640,
                    "8":1747,"9":1860,"R":2400,"GROUP":2247}, "dur":0.040},
}
# ---- aeronautical SELCAL (ARINC): letter -> tone (Hz). 16 tones, no I,N,O ----
SELCAL_TONES = {"A":312.6,"B":346.7,"C":384.6,"D":426.6,"E":473.2,"F":524.8,"G":582.1,"H":645.7,
                "J":716.1,"K":794.3,"L":881.0,"M":977.2,"P":1083.9,"Q":1202.3,"R":1333.5,"S":1479.1}

def _tone(f, dur, amp=0.5):
    t = np.arange(int(dur*FS))/FS
    return amp*np.sin(2*np.pi*f*t)

# ---------- numeric sequential (CCIR/ZVEI1/EEA) ----------
def encode(system, digits):
    S = SETS[system]; seq = []; prev = None
    for d in str(digits):
        key = "R" if d == prev else d
        seq.append(S["freqs"][key]); prev = d
    out = np.concatenate([_tone(f, S["dur"]) for f in seq]) if seq else np.zeros(0)
    return out.astype(np.float64)

def _goertzel(x, f):
    n = len(x); k = 2*np.cos(2*np.pi*f/FS); s0=s1=s2=0.0
    for v in x: s0 = v + k*s1 - s2; s2=s1; s1=s0
    return s1*s1 + s2*s2 - k*s1*s2

def decode(system, samples):
    S = SETS[system]; dur = S["dur"]; slot = int(dur*FS)
    freqs = S["freqs"]; names = list(freqs); fv = [freqs[n] for n in names]
    x = np.asarray(samples, float); out = []; prev = None
    for i in range(0, len(x)-slot+1, slot):
        seg = x[i:i+slot]
        if np.mean(seg**2) < 1e-6: continue
        scores = [_goertzel(seg, f) for f in fv]
        name = names[int(np.argmax(scores))]
        if name == "R": out.append(prev if prev is not None else "0")
        elif name == "GROUP": out.append("g")
        else: out.append(name); prev = name
    return "".join(out)

# ---------- aeronautical SELCAL (dual-tone pairs) ----------
def encode_selcal(code, dur=1.0):
    code = code.upper().replace("-", "")
    if len(code) != 4 or any(c not in SELCAL_TONES for c in code):
        raise ValueError("SELCAL code = 4 letters from A-S (no I,N,O), e.g. AB-CD")
    def pair(a,b): return _tone(SELCAL_TONES[a],dur)+_tone(SELCAL_TONES[b],dur)
    gap = np.zeros(int(0.2*FS))
    return np.concatenate([pair(code[0],code[1]), gap, pair(code[2],code[3])]).astype(np.float64)

def decode_selcal(samples, dur=1.0):
    x = np.asarray(samples, float); slot=int(dur*FS)
    names=list(SELCAL_TONES); fv=[SELCAL_TONES[n] for n in names]
    def topn(seg,n=2):
        sc=[_goertzel(seg,f) for f in fv]; idx=np.argsort(sc)[-n:]; return sorted(names[i] for i in idx)
    # first slot and the slot after the gap
    p1=topn(x[:slot]); gapn=int(0.2*FS); p2=topn(x[slot+gapn:slot+gapn+slot])
    return "".join(p1)+"-"+"".join(p2)

if __name__ == "__main__":
    rng=np.random.default_rng(0)
    for sysname in ["CCIR","ZVEI1","EEA"]:
        code="80216"           # includes a repeated... 8,0,2,1,6 (no repeats); try 1122
        for tc in ["80216","11223"]:
            y=encode(sysname,tc); y=y+rng.normal(0,0.05,len(y)); got=decode(sysname,y)
            print(f"{sysname:6} encode {tc} -> decode {got}  {'OK' if got==tc else 'MISMATCH'}")
    y=encode_selcal("AB-CD"); y=y+rng.normal(0,0.02,len(y))
    print("SELCAL AB-CD ->", decode_selcal(y))
