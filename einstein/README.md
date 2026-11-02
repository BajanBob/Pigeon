# Einstein — weak-signal station log & analysis

A cross-platform (Android / Windows / Linux) **companion app** for weak-signal
VHF/UHF/HF operating, in tribute to Albert Einstein. Einstein is an **honest**
tool: it works *alongside* WSJT-X and Hamlib rather than re-implementing their
decoders — the FT8/FT4/WSPR/Q65/MSK144/FST4W/EME engines are WSJT-X's, refined
over 15+ years, and interoperability matters.

## What v1 does (works on every platform)
- **Logging** with UTC, band (6m/2m/1.25m/70cm/33cm/23cm/HF), mode, callsign, grid.
- **Grid DX** — distance and bearing computed from your Maidenhead grid to each
  station's grid (great-circle), with compass heading.
- **Signal fields** — SNR, frequency drift, integration time.
- **Propagation conditions** — antenna heading, wind, rain, barometric pressure,
  humidity, temperature, per entry, for your ground-wave / troposcatter / ocean-
  scatter studies.
- **WSJT-X import** — paste Band-Activity or `ALL.txt` decode lines; Einstein parses
  mode, SNR, dT, frequency and the callsign/grid and logs them. A cross-platform
  way to capture real FT8/FT4/Q65/MSK144/WSPR decodes.
- **Dashboard** — totals, best DX, weakest SNR, by-band and by-mode breakdowns.
- **Export** — ADIF (for your main logbook) and CSV. Everything on-device.

## Planned (desktop helper — needs raw sockets)
Live capture over **WSJT-X's UDP broadcast**, **rigctld (Hamlib) CAT control** for
IC-9100 / FT-991A / FT-710 / Yaesu SDRs and other 2020-era rigs, and **PSK Reporter**
spotting require raw network/serial sockets, which the desktop (Electron) build's
helper will provide. The settings for `rigctld host:port` and the WSJT-X UDP port
are already captured.

## Modes covered (as log categories)
WSPR, FT8, FT4, MSK144, Q65, FST4W, JT65, 2 m / 70 cm EME, meteor scatter,
troposcatter, and **Ocean Scatter (experimental)** — the last is genuine R&D in the
Pigeon/HOMER line, not an established standard.

Built from the same pipeline as Pigeon; released under tag `einstein-v1.0.0`.
