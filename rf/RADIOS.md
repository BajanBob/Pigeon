# Einstein — Radio / CAT settings & the standalone station engine

Einstein now stands on its own on a PC or Raspberry Pi: it has a **native
audio pipe**, the **codecs**, and the **radio presets** built in — no external
"desktop helper" required. This closes the gap where SSP / drift analysis had
no rig-audio input and there was no TX/PTT/CAT path.

Everything here is **additive** to the in-app WebAudio path: the **Analyzer**
and **Recorder** tabs still read the rig's audio through the browser
(`getUserMedia`) on every platform. This document is about the extra native
layer for the Windows / Linux / Pi build.

All on-air content is **clear text**. zlib compression is reversible and
key-less (not a cipher); no encryption is ever applied to RF.

## Modules (`rf/`)

| File | What it does |
|---|---|
| `einstein_audio.py` | Soundcard capture/playback (PortAudio), device listing, spectrum/SNR + fine-offset analysis — the rig-audio pipe for SSP, drift and the analyzer. |
| `einstein_ptt.py` | PTT / CAT drivers: VOX, serial RTS/DTR, CM108 GPIO, Hamlib rigctld, Icom CI-V (PTT + frequency + mode), Yaesu CAT. |
| `einstein_radios.py` | Tested presets for popular 2020-era rigs (CI-V address, CAT baud, PTT method, audio device, recommended modem). |
| `einstein_afsk.py` | AFSK1200 (VHF FM) + 300-baud HF + Robust 8-FSK weak-signal codecs. |
| `einstein_station.py` | Standalone runner that ties audio + preset + PTT + codecs together. |

The app's **Settings → Radio / CAT** panel mirrors `einstein_radios.py`:
pick your radio and the CI-V address, CAT baud, PTT method and rigctld fields
fill in automatically.

## Quick start (desktop / Pi)

```bash
pip install -r requirements.txt            # numpy, sounddevice, pyserial
cd rf
python3 einstein_station.py --radios       # list supported radios
python3 einstein_station.py --devices      # list soundcards/interfaces
python3 einstein_station.py --radio ic9100 --info
python3 einstein_station.py --radio ic9100 --analyze 3     # pipe rig audio -> SSP/drift
python3 einstein_station.py --radio ft991a --port /dev/ttyUSB0 --tune 144390000
python3 einstein_station.py --radio ic9100 --port /dev/ttyUSB0 --tx-test "DE 8P5AB GK03"
python3 einstein_station.py --radio ic9100 --rx --modem afsk1200 --secs 30
```

## "How do I pipe audio for analysis?"

Feed the rig's receive audio into the computer (the radio's **USB-codec**, or
a soundcard interface / line-in), then either:

- **In the app (any platform):** open the **Analyzer** — it reads that input
  through the browser and shows spectrum, waterfall, peak tone and SNR live.
- **Headless / on-device (PC/Pi):** `einstein_station.py --radio <id> --analyze 3`
  captures a few seconds and prints peak frequency, SNR, noise floor and a
  fine tone offset — the same numbers the SSP sea-Doppler / drift
  discriminator uses.

## Supported radios & interfaces

HF presets suit the Einstein Modem (OFDM) and the HF codecs (AFSK300 / Robust);
FM VHF/UHF presets suit AFSK1200 and, on FM, the 9 kbps Pro VHF modem.

| Radio / interface | PTT | CI-V | CAT baud | Bands | Notes |
|---|---|---|---|---|---|
| Generic soundcard + VOX | VOX | — | — | HF/VHF | SignaLink, Easy Digi; deviate ~3 kHz FM |
| Tigertronics SignaLink USB | VOX | — | — | HF/VHF | Audio "USB Audio CODEC"; DLY low |
| Digirig Mobile | RTS | — | — | HF/VHF | Audio "USB PnP Sound Device" |
| CM108/CM119 USB fob | CM108 | — | — | HF/VHF | Linux `/dev/hidrawN`, GPIO3 |
| Hamlib rigctld (any radio) | RIGCTLD | — | — | HF/VHF | `rigctld -m <model> -r <port> -s <baud>` |
| **Icom IC-9100** | CI-V | **7C** | 9600 | HF/VHF | DATA MOD=USB; USB-D (HF) / FM-D (2m/70cm) |
| **Icom IC-705** | CI-V | **A4** | 9600 | HF/VHF | DATA MOD=USB |
| **Icom IC-9700** | CI-V | **A2** | 9600 | VHF/UHF | FM-D; 9 kbps Pro VHF on FM |
| **Icom IC-7100** | CI-V | **88** | 9600 | HF/VHF | DATA MOD=USB |
| **Icom IC-7300** | CI-V | **94** | 19200 | HF | CI-V USB baud 19200/Auto; USB-D |
| **Icom IC-7610** | CI-V | **98** | 19200 | HF | USB-D |
| **Yaesu FT-991A** | Yaesu CAT | — | 38400 | HF/VHF | CAT on "Standard" COM (menu 031); DATA-FM / DATA-U |
| **Yaesu FT-710 / FTDX10 / FTDX101** | Yaesu CAT | — | 38400 | HF | DATA-U, USB audio |
| Yaesu FT-2980R | VOX | — | — | VHF | Mic + ext-speaker via interface |
| Yaesu FTM-500D / 300D / 200 | VOX | — | — | VHF/UHF | Rear DATA jack, 1200 bps |
| Kenwood TS-590SG / 590S / 890S | rigctld | — | 115200 | HF | USB audio + CAT; rigctld for PTT+tune |
| Kenwood TM-V71A / V71E | VOX | — | — | VHF/UHF | DATA jack, 1200 bps |
| Xiegu X6100 | rigctld | — | — | HF | USB audio + CAT (firmware dependent) |
| Xiegu G90 / G106 | VOX | — | — | HF | DE-19 / Digirig for audio |
| Radtel / Quansheng / Baofeng HTs | DTR | — | — | VHF/UHF | AIOC cable; low power |

> Values are the same tested figures used by the companion **Tradewind** app.
> For any radio not listed, use **Hamlib rigctld** — if `rigctld` supports it,
> Einstein can key and tune it.

## PTT methods

- **VOX** — the interface keys the radio on audio; no control wiring.
- **Serial RTS / DTR** — Digirig, AIOC, Icom USB, home-brew.
- **CM108 GPIO** — CM108/CM119 USB fobs (Linux `/dev/hidrawN`).
- **Hamlib rigctld** — CAT PTT *and* frequency/mode for any Hamlib radio.
- **Icom CI-V** — PTT, frequency and FM-data mode over one USB cable.
- **Yaesu CAT** — `TX1;`/`TX0;`, `FA` (frequency), `MD` (mode) on newer Yaesus.

## Honesty & legal

These drivers assert PTT and set frequency/mode; they do not alter RF content.
Transmit only on bands and modes you are licensed for, and only in clear text
on the amateur service. CI-V addresses and baud rates must match your radio's
menu settings. On Android the app's audio input works for analysis, but native
soundcard TX/PTT/CAT needs the Windows/Linux/Pi build (Android can't reach
USB-serial / soundcards from the app) — the same limitation Tradewind documents.
