# `results/app_data.json` — schema 1.0 (contract for the app)

The app reads **one** file, `results/app_data.json`, and computes nothing. This
document is the contract: field names, types, units and which fields are ready
tonight. Anything not listed here does not go in the file.

- `schema_version` is fixed at `"1.0"` for the submission. A breaking change
  bumps it and this document changes in the same commit.
- Units are in the field names (`_mm`, `_doy`, `_pct`, `_c`). No unitless
  numbers that need a legend to interpret.
- Dates are ISO `YYYY-MM-DD` strings in the local calendar year.
- Day-of-year (`_doy`) is an integer 1–366, counted as Python's
  `date.timetuple().tm_yday`: 1 March is 60 in a common year and 61 in a leap
  year. **Do not turn a DOY back into a date without the year.** The app should
  show it as a month/day label, not as a date.
- Missing values are JSON `null`, never `""`, `-999` or `"unknown"`.
- Numbers are rounded at the source: rainfall 0.1 mm, temperature 0.01 °C,
  wetness and pH 0.01, percentages 0.01.
- Every number in the file is reproducible from
  `notebooks/field_shift.ipynb` and the cached raw data. The file carries
  `meta.raw_cache_sha256` so a reviewer can check that.

## Status of each block

| Block | Ready | Source |
| --- | --- | --- |
| `meta`, `site`, `period` | yes | this notebook |
| `monthly_climatology` | yes | NASA POWER daily 1991–2025 |
| `onset` | yes | this notebook, stated assumption |
| `soil` | yes | SoilGrids v2.0 point extract |
| `crops` | **pending `rules/rules.csv`** | rules table + `crop_windows.csv` |

`data_status` tells the app which blocks are real. Until `crops` is filled,
render the climate panels and a "planting windows land next" placeholder —
do not invent crop values in the app.

## Top level

| Field | Type | Notes |
| --- | --- | --- |
| `schema_version` | string | `"1.0"` |
| `generated_utc` | string | ISO 8601 UTC, when the file was written |
| `data_status` | object | `{"site_climate": "ready"\|"pending", "crop_windows": "ready"\|"pending"}` |
| `meta` | object | provenance, see below |
| `site` | object | `name`, `lat`, `lon`, `scale_note` |
| `period` | object | `start_date`, `end_date`, `n_years` |
| `monthly_climatology` | array[12] | one object per calendar month, Jan→Dec |
| `annual` | object | `rain_mm_mean`, `rain_mm_median`, `n_years_complete` |
| `onset` | object | definition + summary + per-year rows |
| `soil` | object | pH and texture, 0–30 cm depth-weighted |
| `crops` | array | one object per crop, **empty until rules land** |
| `notes` | array[string] | short honesty notes the app may show verbatim |

### `meta`

| Field | Type | Notes |
| --- | --- | --- |
| `sources` | array[object] | `name`, `url`, `accessed` (ISO date) |
| `assumptions` | array[string] | the planting assumption, once, in plain words |
| `raw_cache_sha256` | string | SHA-256 of the POWER CSV the numbers came from |
| `pipeline` | string | e.g. `"notebooks/field_shift.ipynb"` |

## `monthly_climatology[]`

| Field | Type | Unit | Notes |
| --- | --- | --- | --- |
| `month` | int | 1–12 | |
| `rain_mm_mean` | number | mm/month | mean of year totals |
| `rain_mm_median` | number | mm/month | |
| `rain_mm_p25` | number | mm/month | 25th percentile across years |
| `rain_mm_p75` | number | mm/month | 75th percentile |
| `n_years` | int | | years contributing, ≤ 35 |
| `t2m_mean_c` | number | °C | mean daily temperature that month |
| `gwetroot_mean` | number | 0–1 | mean root-zone soil wetness |

Bars or a band chart read `rain_mm_mean` plus `p25`/`p75`. `n_years` below 35
means some months were incomplete and were excluded — show that, do not hide it.

## `onset`

```json
"onset": {
  "definition": {
    "rain_10d_threshold_mm": 20.0,
    "gwetroot_min": 0.40,
    "crossing_rule": "trailing 10-day rain sum >= threshold and previous 10-day sum < threshold",
    "dry_day_mm": 1.0,
    "dry_spell_window_days": 30
  },
  "summary": [
    {
      "season": "first_rains",
      "label": "First rains (Feb–May)",
      "onset_doy_median": 53.0,
      "onset_doy_p25": 41.5,
      "onset_doy_p75": 73.5,
      "years_evaluated": 35,
      "years_found": 35,
      "years_with_dry_spell_ge_7d_in_next_30d": 17
    }
  ],
  "by_year": [
    {
      "year": 1991,
      "season": "first_rains",
      "onset_date": "1991-02-01",
      "onset_doy": 32,
      "onset_found": true,
      "rain_next_30d_mm": 23.1,
      "longest_dry_spell_next_30d": 9
    }
  ]
}
```

`summary[]` gives the app one sentence per season: the median onset and the
spread. `by_year[]` gives the year-by-year strip. `onset_found: false` years
have `onset_date`, `onset_doy` and the dry-spell fields as `null` — plot them as
gaps, not as zero.

The `label` strings are display text and live in this file so the app does not
hardcode season names.

## `soil`

| Field | Type | Unit | Notes |
| --- | --- | --- | --- |
| `ph_h2o` | number | pH | depth-weighted 0–30 cm |
| `clay_pct` | number | % | |
| `sand_pct` | number | % | |
| `silt_pct` | number | % | |
| `texture_sum_pct` | number | % | should be ~100; shown as a data check |

## `crops[]` — pending the rules table

One object per crop, in this fixed order: maize, common bean, finger millet,
sorghum, groundnut. A crop with fewer than three sourced rules is **cut** before
this file is written, so the array length is 3–5.

| Field | Type | Unit | Notes |
| --- | --- | --- | --- |
| `crop` | string | | stable key, e.g. `"common_bean"` |
| `crop_label` | string | | display name |
| `status` | string | | `"sourced"` or `"partial"` (some rules unknown) |
| `documented_window_start_doy` | int\|null | DOY | current practice, from a sourced rule |
| `documented_window_end_doy` | int\|null | DOY | |
| `supported_window_start_doy` | int\|null | DOY | our rules + rainfall |
| `supported_window_end_doy` | int\|null | DOY | |
| `gap_days` | int\|null | days | `supported start − documented start`, signed |
| `rain_threshold_mm_10d` | number\|null | mm | the sourced rule used |
| `season_length_days` | int\|null | days | to maturity |
| `ph_range` | [number, number]\|null | pH | |
| `temp_range_c` | [number, number]\|null | °C | |
| `rules_used` | array[string] | | `rules.csv` row ids or `crop/stage/parameter` keys |
| `unknown_rules` | array[string] | | parameters with no source, shown as "unknown" in the app |

`gap_days` is the point of the app: positive means our supported window starts
later than documented practice.

### Example `crops[]` entry (placeholders — real numbers land with `rules.csv`)

```json
{
  "crop": "common_bean",
  "crop_label": "Common bean",
  "status": "partial",
  "documented_window_start_doy": null,
  "documented_window_end_doy": null,
  "supported_window_start_doy": null,
  "supported_window_end_doy": null,
  "gap_days": null,
  "rain_threshold_mm_10d": null,
  "season_length_days": null,
  "ph_range": null,
  "temp_range_c": null,
  "rules_used": [],
  "unknown_rules": ["planting_rainfall_threshold"]
}
```

## Example top-level skeleton

```json
{
  "schema_version": "1.0",
  "generated_utc": "2026-11-14T21:05:00Z",
  "data_status": { "site_climate": "ready", "crop_windows": "pending" },
  "meta": { "sources": [], "assumptions": [], "raw_cache_sha256": "...", "pipeline": "" },
  "site": { "name": "Nakasongola", "lat": 1.35, "lon": 32.45, "scale_note": "" },
  "period": { "start_date": "1991-01-01", "end_date": "2025-12-31", "n_years": 35 },
  "monthly_climatology": [],
  "annual": { "rain_mm_mean": 1114.4, "rain_mm_median": 1074.8, "n_years_complete": 35 },
  "onset": { "definition": {}, "summary": [], "by_year": [] },
  "soil": { "ph_h2o": 6.12, "clay_pct": 38.57, "sand_pct": 39.63, "silt_pct": 21.8, "texture_sum_pct": 100.0 },
  "crops": [],
  "notes": []
}
```
