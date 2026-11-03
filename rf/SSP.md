# SSP — Sea Scatter Propagation analysis & mode (2 m / 70 cm)

*AI-assisted (Claude). Experimental. Honest, physics-capped — triage, not a promise.*

SSP aggregates the **marine-weather variables that actually drive over-water VHF/UHF
propagation** along the great-circle path between two Maidenhead grid squares, and
produces a **workable-path likelihood** for 2 m (144 MHz) and 70 cm (432 MHz), broken
out by distance band (≤1000 mi, ≤3000 mi, ≤6000 mi, and beyond).

It is both an **analysis tool** (in the app's SSP tab, and `rf/ssp_predict.py`) and a
**logged mode** ("SSP — Sea Scatter (exp)") so you can record and spot the openings you
work.

## The honest physics (why the long bands read ~0)

2 m and 70 cm extend beyond line-of-sight over sea by **tropospheric ducting**
(evaporation ducts, surface/elevated ducts from temperature inversions), **tropo
forward-scatter**, and true **sea-surface Bragg scatter** off the moving water. These
are real and can be spectacular over warm seas — but they are **not** an HF-style
worldwide path. Documented 2 m over-water tropo-ducting records reach roughly
**1,500–4,000 km** in exceptional, *continuous*-duct conditions; 70 cm somewhat less.

So SSP caps each prediction at a physical ceiling (**2 m ≈ 4,000 km, 70 cm ≈ 3,000 km**)
and fades the probability out past it. A 3,000-mile request sits at the extreme edge; a
6,000-mile-plus request returns **NOT SUPPORTED** with a note that the number is shown
for completeness, not as a realistic opening. Einstein will not invent DX that physics
does not allow — and saying so plainly is the point.

## Variables aggregated (per waypoint, then combined along the path)

| Variable | Source | Why it matters |
|---|---|---|
| Sea-surface temperature | Open-Meteo marine | sets surface humidity → evaporation duct |
| Air temperature @2 m | Open-Meteo forecast | air-vs-sea ΔT → surface inversion / duct |
| Relative humidity | Open-Meteo forecast | humidity lapse → modified refractivity M(z) |
| Surface pressure | Open-Meteo forecast | refractivity term |
| Wind speed | Open-Meteo forecast | sea roughness → Bragg-scatter strength |

From these the model computes, at ~11 waypoints along the path:
- **Evaporation duct height (EDH)** from the modified-refractivity profile M(z);
- **Surface-inversion strength** (air warmer than sea → trapping layer);
- **Duct continuity** — the fraction of the path where a duct actually exists (the
  *weakest link* governs, because one non-ducting grid breaks the whole path);
- **Sea-Bragg Doppler** for the band (the characteristic sea-scatter signature).

## The "AI" analysis (transparent, not a black box)

A **logistic model** over the physics features (EDH of the weakest grid, duct-continuity
fraction, mean M-deficit, max inversion, mean SST, a 70 cm penalty, a distance penalty)
outputs the probability. Coefficients are frozen in `ssp_predict.py` so every score is
**reproducible and explainable** — you can read exactly why a path scored as it did. The
hard physical ceiling is applied on top, so the model can never over-promise distance.

## Workflow (app SSP tab)

1. Enter **From** and **To** grid squares; pick **2 m / 70 cm**; pick a **target distance
   band** or leave on *Auto*.
2. Einstein samples **live marine weather** at each waypoint (Open-Meteo, no key); if
   offline it uses one representative set you enter, applied to the whole path.
3. **Run analysis** → distance, bearing, band, EDH, duct-continuity, and
   **P(workable) + verdict** (LIKELY / POSSIBLE / UNLIKELY / NOT SUPPORTED).
4. Send the result to an **optional email**, a **WhatsApp number**, or an **on-screen
   pop-up**.

## Measured examples (`python3 ssp_predict.py`)

```
FK52->FK68  700 km (436 mi), 2 m, warm sea + mild inversion   => 71%  LIKELY
IL38->IM76 1163 km (723 mi), 2 m                              => 60%  POSSIBLE
FK52->(7000 km) 2 m, ideal ducting everywhere                => 0%   NOT SUPPORTED
                                                                (exceeds ~4000 km ceiling)
```

## Files
- `ssp_predict.py` — grid math, path sampling, duct/scatter physics, logistic score,
  physical ceilings, per-band verdicts. `python3 ssp_predict.py` self-tests.
- In-app: the **SSP tab** (same physics ported to on-device JavaScript + live Open-Meteo).

## Legal / honesty
Analysis only — no transmission. Any SSP QSO you log and transmit is **clear-text**
amateur operation on bands you are licensed for. The prediction is a triage estimate from
imperfect weather data and a simplified duct model; treat it as a planning aid, not a
guarantee.
