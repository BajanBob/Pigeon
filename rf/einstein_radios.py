# Einstein — radio / interface presets.
# Adapted from the companion Tradewind project (Brandon St Rose 8P5DG,
# Kammie Holder 8P5AB), MIT License, so Einstein carries the same tested
# CAT addresses, baud rates and PTT wiring for popular 2020-era HF/VHF rigs
# and interfaces — and can stand on its own.
#
# Each entry overrides the defaults when chosen. Fields:
#   id        short key
#   label     human name
#   ptt       VOX | RTS | DTR | CM108 | RIGCTLD | CIV | YAESU_CAT
#   civ_addr  Icom CI-V address (hex string) — CIV ptt only
#   cat_baud  CAT serial baud — CIV / YAESU_CAT
#   bands     "HF" | "VHF/UHF" | "HF/VHF" (what the rig covers)
#   modem     recommended Einstein modem profile for this rig's usual use
#   audio     the audio device name to expect
#   note      wiring + radio-menu setup
#
# Einstein modem choices referenced below:
#   AFSK1200   FM packet / APRS on VHF/UHF FM          (rf/einstein_afsk.py)
#   AFSK300    HF packet on SSB (USB)                  (rf/einstein_afsk.py)
#   ROBUST     weak-signal 8-FSK text on HF/SSB        (rf/einstein_afsk.py)
#   OFDM-STD   Einstein Modem Standard (QPSK ~1 kHz)   (rf/einstein_modem.py)
#   OFDM-PRO   Einstein Modem Pro (16-QAM ~2.4 kHz HF) (rf/einstein_modem.py)
#   OFDM-PROV  Einstein Modem Pro VHF (64-QAM ~9 kbps) (rf/einstein_modem.py)

DEFAULTS = dict(ptt="VOX", civ_addr="7C", cat_baud=9600,
                audio="USB Audio CODEC", sample_rate=48000, modem="AFSK1200")

RADIOS = [
    # ---- generic interfaces ----
    dict(id="generic_vox", label="Generic soundcard + VOX (SignaLink, Easy Digi)",
         ptt="VOX", bands="HF/VHF", modem="AFSK1200",
         note="Turn the interface's VOX/delay knob low. Set TX audio so the radio deviates about 3 kHz (FM) or ALC just moves (SSB)."),
    dict(id="signalink", label="Tigertronics SignaLink USB",
         ptt="VOX", bands="HF/VHF", modem="AFSK1200", audio="USB Audio CODEC",
         note="SignaLink keys the radio itself (VOX): DLY knob ~9 o'clock, TX knob low. Use the jumper/cable for your model's data or mic jack."),
    dict(id="digirig", label="Digirig Mobile",
         ptt="RTS", bands="HF/VHF", modem="AFSK1200", audio="USB PnP Sound Device",
         note="Audio device 'USB PnP Sound Device'. PTT = Serial RTS on the Digirig's serial port (COMx / /dev/ttyUSBx)."),
    dict(id="cm108", label="CM108 / CM119 USB fob with GPIO PTT",
         ptt="CM108", cm108_gpio=3, bands="HF/VHF", modem="AFSK1200",
         note="Linux only: PTT device is /dev/hidrawN (grant access via a udev rule). GPIO3 is typical."),
    dict(id="rigctld", label="Any radio via Hamlib rigctld (CAT PTT + tune)",
         ptt="RIGCTLD", ptt_port="127.0.0.1:4532", bands="HF/VHF", modem="OFDM-PRO",
         note="Start rigctld for your radio first (rigctld -m <model> -r <port> -s <baud>). Pick the radio's USB audio for in/out. Einstein keys and tunes through Hamlib."),

    # ---- Icom (CI-V: PTT, frequency and mode over one USB cable) ----
    dict(id="ic9100", label="Icom IC-9100 (HF/VHF/UHF, USB audio + CI-V)",
         ptt="CIV", civ_addr="7C", cat_baud=9600, bands="HF/VHF", modem="OFDM-PRO",
         audio="USB Audio CODEC",
         note="One USB cable carries audio and CI-V. On the radio: DATA MOD = USB, USB MOD level ~25-50%, CI-V address 7C, CI-V baud 9600. Use USB-D on HF and FM-D on 2m/70cm. Close other CAT software (logger/WSJT-X) first — only one program can use the port."),
    dict(id="ic705", label="Icom IC-705 (HF/VHF/UHF, USB audio + CI-V)",
         ptt="CIV", civ_addr="A4", cat_baud=9600, bands="HF/VHF", modem="OFDM-PRO",
         audio="USB Audio CODEC",
         note="CI-V address A4. DATA MOD = USB; USB-D on HF, FM-D on 2m/70cm. (For VOX-only wiring set PTT=RTS instead, USB SEND=RTS on the radio.)"),
    dict(id="ic9700", label="Icom IC-9700 (VHF/UHF/23cm, USB audio + CI-V)",
         ptt="CIV", civ_addr="A2", cat_baud=9600, bands="VHF/UHF", modem="OFDM-PROV",
         audio="USB Audio CODEC",
         note="CI-V address A2. DATA MOD = USB, FM-D. On FM 2m/70cm you can run the 9 kbps Einstein Pro VHF modem."),
    dict(id="ic7100", label="Icom IC-7100 (HF/VHF/UHF, USB audio + CI-V)",
         ptt="CIV", civ_addr="88", cat_baud=9600, bands="HF/VHF", modem="OFDM-PRO",
         audio="USB Audio CODEC",
         note="CI-V address 88. DATA MOD = USB; USB-D on HF, FM-D on 2m/70cm."),
    dict(id="ic7300", label="Icom IC-7300 (HF/6m, USB audio + CI-V)",
         ptt="CIV", civ_addr="94", cat_baud=19200, bands="HF", modem="OFDM-PRO",
         audio="USB Audio CODEC",
         note="CI-V USB baud 19200 (or Auto), address 94. DATA MOD = USB, use USB-D. Good for HF Einstein Modem, AFSK300 or Robust weak-signal."),
    dict(id="ic7610", label="Icom IC-7610 (HF/6m, USB audio + CI-V)",
         ptt="CIV", civ_addr="98", cat_baud=19200, bands="HF", modem="OFDM-PRO",
         audio="USB Audio CODEC",
         note="CI-V address 98, baud 19200. DATA MOD = USB, USB-D."),

    # ---- Yaesu (text CAT: TX1;/TX0;, FA, MD) ----
    dict(id="ft991a", label="Yaesu FT-991A (HF/VHF/UHF, USB audio)",
         ptt="YAESU_CAT", cat_baud=38400, bands="HF/VHF", modem="OFDM-PRO",
         audio="USB Audio CODEC",
         note="For TX+tune: Yaesu CAT on the 'Standard' COM port at the radio's CAT baud (menu 031, e.g. 38400). Use DATA-FM on 2m/70cm, DATA-U on HF. (RTS-only keying: PTT=RTS on the 'Enhanced' COM port, radio PC-keying=RTS.)"),
    dict(id="ft710", label="Yaesu FT-710 / FTDX10 / FTDX101 (HF, USB audio)",
         ptt="YAESU_CAT", cat_baud=38400, bands="HF", modem="OFDM-PRO",
         audio="USB Audio CODEC",
         note="Yaesu CAT on the 'Standard' COM port at the radio's CAT rate. Select USB as the data/rear audio input and use DATA-U. HF Einstein Modem / AFSK300 / Robust."),
    dict(id="ft2980", label="Yaesu FT-2980R (2m FM, mic+speaker via interface)",
         ptt="VOX", bands="VHF/UHF", modem="AFSK1200", tx_level=0.3,
         note="No data jack or CAT. Use a SignaLink (VOX) or Digirig (RTS) on the 8-pin mic jack + external speaker jack. Check the cable pinout. Keep TX audio low (pre-emphasised) and use Low/Mid power."),
    dict(id="yaesu_ftm", label="Yaesu FTM-500D / FTM-300D / FTM-200 (DATA jack)",
         ptt="VOX", bands="VHF/UHF", modem="AFSK1200",
         note="Soundcard interface on the rear DATA jack (cable for your model), data-jack speed 1200 bps, radio's own APRS off. PTT: VOX, or Serial RTS on a Digirig."),

    # ---- Kenwood ----
    dict(id="ts590", label="Kenwood TS-590SG / TS-590S / TS-890S (HF, USB audio)",
         ptt="RIGCTLD", ptt_port="127.0.0.1:4532", cat_baud=115200, bands="HF", modem="OFDM-PRO",
         audio="USB Audio CODEC",
         note="One USB cable carries audio and CAT. Run Hamlib rigctld for your model for PTT+tune; set the radio's data input to USB audio. HF Einstein Modem / AFSK300 / Robust."),
    dict(id="tmv71", label="Kenwood TM-V71A / TM-V71E (2m/70cm, DATA jack)",
         ptt="VOX", bands="VHF/UHF", modem="AFSK1200",
         note="6-pin mini-DIN DATA jack with a SignaLink (VOX) or Digirig (RTS). Set the data band and 1200 bps in the menu."),

    # ---- Xiegu / QRP / handhelds ----
    dict(id="x6100", label="Xiegu X6100 (HF/6m, USB audio)",
         ptt="RIGCTLD", ptt_port="127.0.0.1:4532", bands="HF", modem="OFDM-STD",
         audio="USB Audio CODEC",
         note="Audio + CAT over USB (firmware dependent). Run Hamlib rigctld with the X6100 model. HF Einstein Modem / AFSK300 / Robust."),
    dict(id="xiegu_g90", label="Xiegu G90 / G106 (HF, via DE-19 / Digirig)",
         ptt="VOX", bands="HF", modem="OFDM-STD",
         note="No built-in sound card — use the DE-19 or a Digirig for audio. PTT: VOX, Serial RTS (Digirig) or rigctld via the CI-V port."),
    dict(id="aioc_ht", label="Radtel RT-890/RT-4D, Quansheng UV-K5, Baofeng UV-5R (AIOC)",
         ptt="DTR", bands="VHF/UHF", modem="AFSK1200", tx_level=0.3, audio="All-In-One-Cable",
         note="AIOC all-in-one cable (Kenwood 2-pin): audio 'All-In-One-Cable', PTT = DTR. Radio VOX off, TX audio low, squelch just closed, low power (HTs aren't made for long transmissions)."),
]

_BY_ID = {r["id"]: r for r in RADIOS}


def get(radio_id):
    """Return a full config dict for a radio id (defaults merged in)."""
    r = _BY_ID.get(radio_id)
    if not r:
        raise KeyError(f"unknown radio id: {radio_id}")
    cfg = dict(DEFAULTS)
    cfg.update(r)
    return cfg


def list_ids():
    return [r["id"] for r in RADIOS]


def cat_params(radio_id):
    """Just the keying/tuning fields, ready for einstein_ptt.make_ptt()."""
    c = get(radio_id)
    return dict(kind=c["ptt"], civ_addr=c.get("civ_addr", "7C"),
                baud=c.get("cat_baud", 9600),
                rigctld=c.get("ptt_port", "127.0.0.1:4532"),
                cm108_gpio=c.get("cm108_gpio", 3))


if __name__ == "__main__":
    print(f"{len(RADIOS)} radio presets\n")
    print(f"{'id':14s} {'ptt':10s} {'CI-V':5s} {'baud':6s} {'band':8s} {'modem':9s} label")
    print("-" * 100)
    for r in RADIOS:
        c = get(r["id"])
        civ = c["civ_addr"] if c["ptt"] == "CIV" else "-"
        baud = c["cat_baud"] if c["ptt"] in ("CIV", "YAESU_CAT") else "-"
        print(f"{c['id']:14s} {c['ptt']:10s} {str(civ):5s} {str(baud):6s} "
              f"{c.get('bands',''):8s} {c.get('modem',''):9s} {c['label']}")
    # sanity: every preset builds a PTT driver
    import einstein_ptt as ptt
    for rid in list_ids():
        ptt.make_ptt(port="/dev/ttyUSB0", **cat_params(rid))
    print("\nAll presets build a PTT driver OK.")
