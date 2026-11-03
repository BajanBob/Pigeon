# Einstein — RF modes library.
# A structured reference of known amateur/utility transmission modes (data,
# voice, image, video) with their key parameters, plus query helpers so the
# app and the cognitive engine can answer "what fits in this bandwidth?".
#
# Figures are best-effort typical values from public specifications; some
# proprietary modes (PACTOR III/IV, VARA) are approximate/edge figures and are
# flagged. Bandwidths are occupied/necessary bandwidth in Hz. "snr_db" is an
# indicative decode threshold in a 2500 Hz reference where well known.
"""
Fields per mode:
  id, name, cat (category), kind (data|voice|image|video),
  baud (symbol/baud rate), rate (user throughput), bw_hz (occupied BW, Hz),
  mod (modulation), coding (FEC / error control / algorithm),
  enc (source/line encoding), ss (spread-spectrum type or None),
  snr_db (indicative threshold, or None), notes.

Helpers:
  all_modes(), by_category(cat), by_kind(kind), get(id)
  fits(bw_hz)      -> modes whose occupied BW <= bw_hz
  categories(), summary()
"""

MODES = [
  # ---------------- CW ----------------
  dict(id="cw", name="CW (Morse)", cat="CW", kind="data", baud="5–40 WPM",
       rate="~10–50 bps", bw_hz=150, mod="OOK (A1A)", coding="none",
       enc="Morse", ss=None, snr_db=-18,
       notes="Bandwidth ~ 4*WPM/1.2 Hz; 150 Hz is a typical 25 WPM keying BW."),

  # ---------------- HF keyboard / chat ----------------
  dict(id="rtty", name="RTTY (Baudot)", cat="HF keyboard", kind="data",
       baud="45.45", rate="~60 WPM / ~45 bps", bw_hz=300, mod="FSK, 170 Hz shift",
       coding="none", enc="Baudot ITA2 (5-bit)", ss=None, snr_db=-6,
       notes="Classic 45.45 baud / 170 Hz. Also 50/75/100 baud variants."),
  dict(id="psk31", name="PSK31", cat="HF keyboard", kind="data", baud="31.25",
       rate="~50 WPM / ~31.25 sym/s", bw_hz=60, mod="BPSK (QPSK variant adds FEC)",
       coding="none (BPSK); convolutional (QPSK)", enc="Varicode", ss=None, snr_db=-10,
       notes="Very narrow; raised-cosine filtered. PSK63/125/250 scale BW with baud."),
  dict(id="mfsk16", name="MFSK16", cat="HF keyboard", kind="data", baud="15.625",
       rate="~42 WPM", bw_hz=316, mod="16-FSK", coding="convolutional r=1/2 K=7",
       enc="Varicode", ss=None, snr_db=-13, notes="Robust HF chat; good on flutter."),
  dict(id="olivia", name="Olivia (e.g. 32/1000)", cat="HF keyboard", kind="data",
       baud="31.25 (32-tone)", rate="~ slow", bw_hz=1000, mod="MFSK (32 tones)",
       coding="Walsh/Hadamard FEC", enc="7-bit ASCII blocks", ss=None, snr_db=-14,
       notes="Extremely robust; many tone/bandwidth combos (e.g. 8/250, 16/500, 32/1000)."),
  dict(id="contestia", name="Contestia", cat="HF keyboard", kind="data", baud="varies",
       rate="~2x Olivia speed", bw_hz=500, mod="MFSK", coding="Walsh FEC",
       enc="6-bit varicode", ss=None, snr_db=-13, notes="Faster, slightly less robust Olivia."),
  dict(id="thor", name="THOR / DominoEX", cat="HF keyboard", kind="data", baud="varies",
       rate="~slow–medium", bw_hz=260, mod="IFK+ MFSK", coding="convolutional (THOR)",
       enc="Varicode / MFSK", ss=None, snr_db=-12, notes="Incremental-frequency keying; NVIS/aurora tolerant."),
  dict(id="feldhell", name="Hellschreiber (Feld Hell)", cat="HF keyboard", kind="image",
       baud="122.5 dots/s", rate="~2.5 char/s", bw_hz=245, mod="OOK fuzzy-mode",
       coding="none (visual redundancy)", enc="Column-scan pixels", ss=None, snr_db=-10,
       notes="Facsimile-style text painted on a waterfall; read by eye."),
  dict(id="fsq", name="FSQ (FSQCall)", cat="HF keyboard", kind="data", baud="varies",
       rate="low", bw_hz=300, mod="IFK+ 33-tone", coding="none", enc="code tables",
       ss=None, snr_db=-12, notes="NVIS selective-calling, store-and-forward on HF."),

  # ---------------- WSJT-X weak signal ----------------
  dict(id="ft8", name="FT8", cat="Weak-signal (WSJT-X)", kind="data", baud="6.25",
       rate="77-bit msg / 15 s", bw_hz=50, mod="8-GFSK (8 tones x 6.25 Hz)",
       coding="LDPC(174,91) + CRC-14", enc="source-encoded 77-bit", ss=None, snr_db=-21,
       notes="15 s T/R. The workhorse for marginal openings; decodes well below the noise."),
  dict(id="ft4", name="FT4", cat="Weak-signal (WSJT-X)", kind="data", baud="20.833",
       rate="77-bit msg / 7.5 s", bw_hz=83, mod="4-GFSK", coding="LDPC(174,91)+CRC",
       enc="77-bit", ss=None, snr_db=-18, notes="Contest-speed FT8 cousin."),
  dict(id="jt65", name="JT65 (A/B/C)", cat="Weak-signal (WSJT-X)", kind="data", baud="2.69",
       rate="1 msg / 60 s", bw_hz=178, mod="65-FSK", coding="Reed–Solomon (63,12)",
       enc="source 72-bit", ss=None, snr_db=-25, notes="EME/weak HF; A=178 Hz, wider for VHF."),
  dict(id="jt9", name="JT9", cat="Weak-signal (WSJT-X)", kind="data", baud="1.736",
       rate="1 msg / 60 s", bw_hz=16, mod="9-FSK", coding="convolutional/LDPC",
       enc="72-bit", ss=None, snr_db=-27, notes="Very narrow LF/MF/HF weak-signal."),
  dict(id="wspr", name="WSPR", cat="Weak-signal (WSJT-X)", kind="data", baud="1.4648",
       rate="beacon 50-bit / 110.6 s", bw_hz=6, mod="4-FSK (continuous-phase)",
       coding="convolutional K=32 r=1/2", enc="50-bit (call/grid/power)", ss=None, snr_db=-31,
       notes="Propagation beacon; ~6 Hz wide. Threshold ~ -31 dB in 2500 Hz."),
  dict(id="fst4", name="FST4 / FST4W", cat="Weak-signal (WSJT-X)", kind="data", baud="varies",
       rate="msg over 15–1800 s", bw_hz=33, mod="4-GFSK", coding="LDPC(240,101)",
       enc="77/50-bit", ss=None, snr_db=-40, notes="LF/MF DX & beacon; -40 dB at 1800 s T/R."),
  dict(id="q65", name="Q65", cat="Weak-signal (WSJT-X)", kind="data", baud="varies (submodes A–E)",
       rate="msg over 15–300 s", bw_hz=200, mod="65-tone FSK + sync tone",
       coding="Q-ary Reed–Solomon (LDPC in newer)", enc="source 13/15 GB", ss=None, snr_db=-28,
       notes="Best for ionoscatter, TEP, EME, aircraft/meteor. Tone spacing set by submode."),
  dict(id="msk144", name="MSK144", cat="Weak-signal (WSJT-X)", kind="data", baud="2000",
       rate="short bursts", bw_hz=2500, mod="offset MSK", coding="LDPC(128,80)",
       enc="77-bit", ss=None, snr_db=-8, notes="Meteor scatter; very fast short pings fill ~2.4 kHz."),

  # ---------------- Digital voice ----------------
  dict(id="freedv", name="FreeDV (700D / 1600 / 2020)", cat="Digital voice", kind="voice",
       baud="OFDM carriers", rate="700–1600 bps voice", bw_hz=1250, mod="OFDM QPSK + pilots",
       coding="LDPC", enc="Codec2 (LPCNet in 2020)", ss=None, snr_db=-2,
       notes="Open HF/VHF digital voice in an SSB passband; 700D robust to ~ -2 dB."),
  dict(id="dstar", name="D-STAR (DV)", cat="Digital voice", kind="voice", baud="4800 sym/s",
       rate="2400 voice + 1200 FEC + 1200 data/sync", bw_hz=6250, mod="GMSK (BT=0.5)",
       coding="convolutional on voice", enc="AMBE (2020)", ss=None, snr_db=None,
       notes="6.25 kHz narrowband FM-family. Icom-led."),
  dict(id="dmr", name="DMR", cat="Digital voice", kind="voice", baud="4800 sym/s (9600 bps)",
       rate="2-slot TDMA", bw_hz=12500, mod="4FSK (C4FM-like)", coding="BPTC/Golay/Hamming",
       enc="AMBE+2 (2450 bps)", ss=None, snr_db=None, notes="12.5 kHz 2-slot TDMA; ETSI TS 102 361."),
  dict(id="c4fm", name="C4FM / System Fusion (YSF)", cat="Digital voice", kind="voice",
       baud="4800 sym/s (9600 bps)", rate="DN/VW modes", bw_hz=12500, mod="4FSK",
       coding="Trellis/FEC", enc="AMBE+2", ss=None, snr_db=None, notes="Yaesu Fusion; 12.5 kHz."),
  dict(id="p25", name="P25 (Phase 1 / 2)", cat="Digital voice", kind="voice",
       baud="4800 sym/s (P1) / 6000 (P2)", rate="9600 bps", bw_hz=12500, mod="C4FM (P1) / H-CPM/H-DQPSK (P2)",
       coding="Reed–Solomon/Golay/Hamming", enc="IMBE (P1) / AMBE+2 (P2)", ss=None, snr_db=None,
       notes="Public-safety; P2 is 6.25 kHz-equivalent 2-slot TDMA."),
  dict(id="nxdn", name="NXDN", cat="Digital voice", kind="voice", baud="2400/4800 sym/s",
       rate="4800/9600 bps", bw_hz=6250, mod="4FSK", coding="trellis/FEC", enc="AMBE+2",
       ss=None, snr_db=None, notes="Icom/Kenwood; true 6.25 kHz option."),
  dict(id="m17", name="M17", cat="Digital voice", kind="voice", baud="4800 sym/s (9600 bps)",
       rate="3200 bps voice", bw_hz=9000, mod="4FSK (RRC)", coding="convolutional/punctured",
       enc="Codec2 3200", ss=None, snr_db=None, notes="Open-source digital voice+data; 9 kHz."),

  # ---------------- Packet / ARQ data ----------------
  dict(id="afsk1200", name="AFSK 1200 (Bell 202)", cat="Packet / data", kind="data",
       baud="1200", rate="1200 bps raw", bw_hz=2600, mod="AFSK 1200/2200 Hz on FM",
       coding="CRC-16 (AX.25 FCS)", enc="NRZI + bit-stuffing (HDLC)", ss=None, snr_db=None,
       notes="VHF/UHF packet & APRS. Einstein ships this (rf/einstein_afsk.py)."),
  dict(id="afsk300", name="HF packet 300 baud", cat="Packet / data", kind="data",
       baud="300", rate="300 bps raw", bw_hz=500, mod="AFSK 200 Hz shift on SSB",
       coding="CRC-16", enc="NRZI/HDLC", ss=None, snr_db=None, notes="Classic HF APRS/packet."),
  dict(id="g3ruh9600", name="9600 G3RUH", cat="Packet / data", kind="data", baud="9600",
       rate="9600 bps raw", bw_hz=16000, mod="direct FSK (baseband into FM)",
       coding="CRC-16", enc="scrambled NRZ", ss=None, snr_db=None,
       notes="Needs a 9600 data port; ~15–20 kHz on FM."),
  dict(id="pactor1", name="PACTOR-I", cat="Packet / data", kind="data", baud="100/200",
       rate="~200 bps", bw_hz=500, mod="FSK", coding="Huffman + CRC ARQ", enc="ASCII/Huffman",
       ss=None, snr_db=None, notes="HF ARQ; open spec."),
  dict(id="pactor3", name="PACTOR-III", cat="Packet / data", kind="data", baud="multi-tone",
       rate="up to ~3600 bps raw / ~5200 compressed (approx)", bw_hz=2400,
       mod="2–18 tone DPSK", coding="adaptive FEC + ARQ", enc="online compression",
       ss=None, snr_db=None, notes="Proprietary (SCS). Figures approximate."),
  dict(id="pactor4", name="PACTOR-IV", cat="Packet / data", kind="data", baud="adaptive",
       rate="up to ~5800 bps (approx)", bw_hz=2400, mod="adaptive PSK/QAM OFDM-like",
       coding="LDPC-class + ARQ", enc="compression", ss=None, snr_db=None,
       notes="Proprietary (SCS); edge figures approximate."),
  dict(id="varahf", name="VARA HF", cat="Packet / data", kind="data", baud="OFDM",
       rate="up to ~7000+ bps (approx)", bw_hz=2300, mod="OFDM (adaptive QAM)",
       coding="adaptive FEC + ARQ", enc="compression", ss=None, snr_db=None,
       notes="Proprietary; the common Winlink HF modem. Figures approximate."),
  dict(id="varafm", name="VARA FM", cat="Packet / data", kind="data", baud="OFDM",
       rate="up to ~25 kbps wide / ~9.6k narrow (approx)", bw_hz=12500, mod="OFDM",
       coding="adaptive FEC + ARQ", enc="compression", ss=None, snr_db=None,
       notes="Proprietary FM-channel Winlink modem."),
  dict(id="ardop", name="ARDOP", cat="Packet / data", kind="data", baud="adaptive",
       rate="~200–8000 bps", bw_hz=2200, mod="OFDM/4FSK adaptive", coding="FEC + ARQ",
       enc="compression", ss=None, snr_db=None, notes="Open Winlink HF modem."),
  dict(id="einstein_ofdm", name="Einstein Modem (OFDM)", cat="Packet / data", kind="data",
       baud="OFDM", rate="~0.56 / 2.7 / 9 kbps (STD/PRO/PRO-VHF, measured)", bw_hz=2400,
       mod="OFDM QPSK/16-QAM/64-QAM", coding="conv r=1/2 K=7 + Viterbi, zlib, ARQ",
       enc="clear text, zlib (reversible)", ss=None, snr_db=2,
       notes="Einstein-native. PRO-VHF 64-QAM ~6 kHz on FM. See rf/MODEM.md."),
  dict(id="einstein_robust", name="Einstein Robust (8-FSK)", cat="Packet / data", kind="data",
       baud="31.25", rate="~44 bps", bw_hz=250, mod="8-FSK", coding="conv r=1/2 K=7 + soft Viterbi, CRC",
       enc="clear text", ss=None, snr_db=-10, notes="Einstein weak-signal HF text (rf/einstein_afsk.py)."),

  # ---------------- Commercial / EmComm (Beryl) ----------------
  dict(id="beryl_lpi", name="Beryl SS (DSSS)", cat="Commercial / EmComm", kind="data",
       baud="chip rate", rate="depends on spreading factor", bw_hz=20000,
       mod="BPSK direct-sequence spread spectrum", coding="PN gain + AES-256-GCM auth",
       enc="clear/ciphertext (commercial only)", ss="DSSS", snr_db=-9,
       notes="COMMERCIAL 148–174 MHz ONLY, band-gated, ID required. Spread-spectrum "
             "anti-jam, below-noise-floor robustness. See rf/BERYL.md. Never on amateur bands."),
  dict(id="beryl_ultra", name="Beryl ultrasonic (data-over-sound)", cat="Commercial / EmComm",
       kind="data", baud="100", rate="~100 bps", bw_hz=1000,
       mod="BFSK 18.5/19.5 kHz (near-ultrasound)", coding="CRC-8 + sync preamble",
       enc="clear/ciphertext", ss=None, snr_db=None,
       notes="ACOUSTIC, not RF. Short-range (~m) RF-free key/config/message transfer. "
             "Needs ~20 kHz-capable speaker/mic. Wrap payload with Beryl AES."),

  # ---------------- Image / fax ----------------
  dict(id="sstv", name="SSTV (Scottie/Martin/PD/Robot)", cat="Image", kind="image",
       baud="analog", rate="8–270 s/frame", bw_hz=2300, mod="FM subcarrier 1500–2300 Hz in SSB",
       coding="none (VIS header)", enc="line-scan FM", ss=None, snr_db=None,
       notes="Fits an SSB passband. Mode sets resolution/time (e.g. Scottie S1, Martin M1, PD120)."),
  dict(id="wefax", name="WEFAX (HF weather fax)", cat="Image", kind="image", baud="120 lpm",
       rate="IOC 576", bw_hz=1900, mod="FM 1500–2300 Hz on SSB", coding="none", enc="line-scan",
       ss=None, snr_db=None, notes="Marine/aviation weather charts; 120 lines/min standard."),
  dict(id="drm", name="DRM (Digital Radio Mondiale)", cat="Broadcast data", kind="voice",
       baud="OFDM", rate="audio + data", bw_hz=10000, mod="COFDM (QAM)", coding="multilevel FEC",
       enc="xHE-AAC/AAC", ss=None, snr_db=None, notes="4.5/5/9/10/18/20 kHz robustness modes."),

  # ---------------- Spread spectrum ----------------
  dict(id="dsss", name="DSSS (direct-sequence)", cat="Spread spectrum", kind="data",
       baud="chip rate (Mcps)", rate="depends on code", bw_hz=1000000, mod="PN-coded PSK",
       coding="PN processing gain = chip/bit", enc="PN sequence (Gold/Barker)", ss="DSSS",
       snr_db=None, notes="Amateur SS on 902/2400/5650 MHz; BW = chip rate (≥~1 MHz)."),
  dict(id="fhss", name="FHSS (frequency-hopping)", cat="Spread spectrum", kind="data",
       baud="hop rate", rate="per-dwell payload", bw_hz=2000000, mod="FSK/PSK per hop",
       coding="per-hop FEC", enc="hop sequence", ss="FHSS", snr_db=None,
       notes="Hops across a band; occupied BW = hop span. 2.4/5 GHz."),
  dict(id="lora", name="LoRa (CSS chirp)", cat="Spread spectrum", kind="data",
       baud="SF7–SF12", rate="~0.25–37.5 kbps", bw_hz=125000, mod="chirp spread spectrum",
       coding="Hamming FEC (CR 4/5–4/8)", enc="chirp symbols", ss="CSS",
       snr_db=-20, notes="BW 125/250/500 kHz; used on 33cm/70cm (not a traditional ham mode)."),

  # ---------------- Video ----------------
  dict(id="atv_ntsc", name="Fast-scan ATV (NTSC)", cat="Video", kind="video", baud="analog",
       rate="30 fps 525-line", bw_hz=6000000, mod="AM-VSB or FM", coding="none",
       enc="analog composite", ss=None, snr_db=None,
       notes="~6 MHz (NTSC) / 7–8 MHz (PAL). 70cm/23cm and up. Far beyond any soundcard."),
  dict(id="datv_dvbs", name="DATV DVB-S", cat="Video", kind="video", baud="125 kS–several MS/s",
       rate="SR-dependent", bw_hz=1500000, mod="QPSK", coding="Viterbi+Reed–Solomon",
       enc="MPEG-2/H.264 TS", ss=None, snr_db=None,
       notes="Occupied BW ≈ 1.35 x symbol rate. Needs an SDR/TV front-end with MHz of BW."),
  dict(id="datv_dvbs2", name="DATV DVB-S2", cat="Video", kind="video", baud="programmable SR",
       rate="ACM adaptive", bw_hz=500000, mod="QPSK/8PSK/16/32APSK", coding="LDPC+BCH",
       enc="H.264/H.265 TS", ss=None, snr_db=None,
       notes="RB-TV (reduced-bandwidth) down to ~66–333 kS (~0.1–0.5 MHz). Still MHz-class."),
  dict(id="dvbt", name="DATV DVB-T (COFDM)", cat="Video", kind="video", baud="OFDM",
       rate="multi-Mbps", bw_hz=2000000, mod="COFDM (1705/6817 carriers)",
       coding="LDPC/convolutional + RS", enc="H.264 TS", ss=None, snr_db=None,
       notes="Robust multipath DATV; 1–8 MHz channels."),
]

_BY_ID = {m["id"]: m for m in MODES}


def all_modes():
    return list(MODES)


def get(mode_id):
    return _BY_ID[mode_id]


def categories():
    out = []
    for m in MODES:
        if m["cat"] not in out:
            out.append(m["cat"])
    return out


def by_category(cat):
    return [m for m in MODES if m["cat"] == cat]


def by_kind(kind):
    return [m for m in MODES if m["kind"] == kind]


def fits(bw_hz):
    """Modes whose occupied bandwidth fits within bw_hz (sorted narrow→wide)."""
    return sorted([m for m in MODES if m["bw_hz"] <= bw_hz], key=lambda m: m["bw_hz"])


def summary():
    return {"modes": len(MODES), "categories": len(categories()),
            "narrowest": min(MODES, key=lambda m: m["bw_hz"])["id"],
            "widest": max(MODES, key=lambda m: m["bw_hz"])["id"]}


def _fmt_bw(hz):
    if hz >= 1e6:
        return f"{hz/1e6:g} MHz"
    if hz >= 1e3:
        return f"{hz/1e3:g} kHz"
    return f"{hz:g} Hz"


if __name__ == "__main__":
    import json, sys
    if "--json" in sys.argv:
        print(json.dumps(MODES, indent=2)); raise SystemExit
    print(f"{len(MODES)} modes in {len(categories())} categories\n")
    for c in categories():
        print(f"== {c} ==")
        for m in by_category(c):
            print(f"  {m['name']:34s} {_fmt_bw(m['bw_hz']):>9s}  {m['mod']}")
    print("\nFits in a 2.7 kHz SSB passband:",
          ", ".join(m["id"] for m in fits(2700)))
    print("\nFits in 24 kHz (48 kHz soundcard Nyquist):",
          len(fits(24000)), "modes")
    print("Need > 24 kHz (wideband/SDR only):",
          ", ".join(m["id"] for m in MODES if m["bw_hz"] > 24000))
    print("\nsummary:", summary())
