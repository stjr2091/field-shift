# Sources

Every number in the deliverables cites its source. Where a rule has no source, it is marked unknown.

Checked so far (links to be added as each is pulled into the repo):

1. MAAIF maize production manual
2. MAAIF beans production manual
3. Finger millet report (full citation to add)
4. 2022 Rakai/Nakasongola planting-date trial (full citation to add)

## Climate data — NASA POWER

- **Product:** NASA POWER (Prediction Of Worldwide Energy Resources) API,
  `temporal/daily/point`, community `AG` (agroclimatology).
- **Parameters:**
  - `PRECTOTCORR` — MERRA-2 precipitation corrected, mm/day
  - `T2M` — MERRA-2 temperature at 2 m, °C
  - `GWETROOT` — MERRA-2 root-zone soil wetness, 0–1 (fraction of saturation)
- **Point:** latitude 1.79, longitude 33.50 (Soroti). POWER serves one
  MERRA-2 grid cell of about 0.5° × 0.625° (roughly 50 km), so every value is
  **district-scale, not parcel-scale**. This is a limit we state, not hide.
- **Period:** 1991-01-01 to 2025-12-31 (12,784 days, complete, no sentinels).
- **Access:** no key, no login. 14 Nov 2026.
- **Exact URL** (also in `scripts/download_data.py` and inside
  `results/site_climate.json`):

  ```
  https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR,T2M,GWETROOT&community=AG&longitude=33.5&latitude=1.79&start=19910101&end=20251231&format=CSV
  ```

- **Missing data:** POWER writes `-999` where a value cannot be computed. The
  pipeline converts it to NaN and reports the count (`data_quality` in
  `results/site_climate.json`); it is never summed as a number. This pull has
  zero `-999` values.
- **Cache:** `data/raw/power_daily_1.79N_33.50E_1991-2025.csv`, not in git. The
  output JSON records its SHA-256 so any published number can be checked against
  the exact bytes it came from.

## Soil data — ISRIC SoilGrids v2.0

- **Product:** ISRIC SoilGrids REST API v2.0, point query.
- **Properties:** `phh2o` (pH in water), `clay`, `sand`, `silt` at 0–5,
  5–15 and 15–30 cm; `value=mean` and `value=Q0.5` (median).
- **Units as returned:** texture in g/kg (divide by 10 for %), pH as pH × 10
  (divide by 10). The pipeline applies both conversions in
  `notebooks/field_shift_data.py::read_soilgrids`.
- **Point:** latitude 1.79, longitude 33.50, the same site point as POWER.
  SoilGrids is a 250 m product, so this is site-level soil, not district soil.
- **Exact URL** (also in `scripts/download_data.py` and inside
  `results/site_climate.json`):

  ```
  https://rest.isric.org/soilgrids/v2.0/properties/query?lon=33.5&lat=1.79&property=phh2o&property=clay&property=sand&property=silt&depth=0-5cm&depth=5-15cm&depth=15-30cm&value=mean&value=Q0.5
  ```

- **Fragility and fallback:** the live query takes about 30 s and the public
  service is occasionally rate-limited, so the extract is **committed** at
  `data/processed/soilgrids_site.json` together with this URL and the access
  date. `scripts/download_data.py` falls back to that committed copy when the
  live query fails, and says so on stderr. A reader can therefore rebuild
  `results/site_climate.json` without any network access.
- **Access:** no key, no login. 14 Nov 2026.

## Access dates

| Source | Accessed | Where the exact URL is recorded |
| --- | --- | --- |
| NASA POWER daily point | 2026-11-14 | `SOURCES.md`, `scripts/download_data.py`, `results/site_climate.json` |
| ISRIC SoilGrids v2.0 | 2026-11-14 | `SOURCES.md`, `scripts/download_data.py`, `results/site_climate.json` |
