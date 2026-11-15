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
| `crops` | yes, from `rules/rules.csv` | rules table; three crops pass the three-of-four cut |

`data_status` tells the app which blocks are real. A crop appears only when at
least three of its four parameters have a sourced row, per `docs/plan.md`. A crop
with fewer is cut and the app says so; no crop value is invented to fill a gap.
See `docs/crop_rules.md` for what the table supports.

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
| `annual` | object | `rain_mm_mean`, `rain_mm_median`, `n_years_complete`, `t2m_mean_c` |
| `onset` | object | definition + summary + per-year rows |
| `soil` | object | pH and texture, 0–30 cm depth-weighted |
| `crops` | array | one object per crop; a crop with fewer than three sourced rules is cut |
| `crop_rule_coverage` | array[object] | sourced rows per crop out of four, whether it appears, and the reason when it is cut |
| `crop_rotation` | array[object] | rotation directions a source backs |
| `sequence_reasons` | array[object] | rotation reasons a previous-crop choice can match, each with its own label |
| `crop_path_assumption` | string | the one-step model, stated plainly: each crop affects only the crop that follows it |
| `crop_limitations` | array[string] | the five limitation lines from the released rules table |
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
| `season_length_days` | int\|null | days | shortest published duration, to maturity |
| `season_length_days_max` | int\|null | days | longest published duration, so the page can state both ends |
| `ph_range` | [number, number]\|null | pH | |
| `temp_range_c` | [number, number]\|null | °C | |
| `rules_used` | array[string] | | `rules.csv` row ids or `crop/stage/parameter` keys |
| `unknown_rules` | array[string] | | parameters with no source, shown as "unknown" in the app |
| `unknown_notes` | object | | one plain sentence per unknown parameter, so a gap is stated and not left blank |
| `source_label` | string\|null | | short line the app prints in place of the rule source; set when the only gap is the rainfall threshold |

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

## `sequence_reasons[]`

One object per rotation reason a previous-crop choice can match. The app reads
the list and keeps the choice order itself.

| Field | Type | Notes |
| --- | --- | --- |
| `previous_crop` | string | crop key the reason starts from |
| `candidate` | string | crop key the reason applies to |
| `label` | string | `"survey"` or `"assumption"`; never shown as computed |
| `direction` | string | `"for"` or `"against"` the candidate |
| `reason` | string | one plain sentence |
| `note` | string | what backs it, and the limit of that backing |

Rows are generated from `notebooks/crop_path.py`, which the notebook and the
build both call. A pair row tagged `assumed` is team expertise for this
prototype, written as a direction with no number. A row tagged `sourced` is
farmer knowledge from a survey. Neither is a measured rotation effect.

## Ordered paths

A crop path is a list of crop keys in order, for example
`["maize", "common_bean", "finger_millet"]`. It is read pair by pair:
`maize->common_bean` then `common_bean->finger_millet`. The path is kept as a
path and is never collapsed to a set, so two paths with the same crops in a
different order give a different result.

The model assumes each crop affects only the crop that follows it. It does not
test a crop against a crop two steps back.

## The path index

`results/path_index.json` is a build-time lookup for screens that need the
ordered-path comparison without a server. One build writes it with
`results/app_data.json`, so the two cannot drift.

The key is the crop path, newest last, with segments joined by `>`. For example
`maize>common_bean>finger_millet`.

Each value carries the fields a screen renders, under the same names the model
returns: `steps`, `n_steps`, `n_matched`, `n_for`, `n_against`, `n_unmatched`
and `path_labels`. Each step carries `from`, `to`, `matched`, `label`,
`direction`, `reason` and `note`. There is no translation layer.

The value is a subset of the model's result. `path` and `assumption` are
dropped, because the key already states the path and the assumption is one
statement for the whole file. A screen shows the one-step assumption from
`crop_path_assumption` in `results/app_data.json`, not from this file.

Every entry is produced by calling the model. The index is a projection of
`notebooks/crop_path.py`, not a second implementation.

It covers the five crop keys at lengths 1 to 3. Length 1 is included, so a
single-crop request returns an empty result rather than a missing key.

## What the screen must do before it looks up

1. Read `prev-1` first. It is the crop grown last. Look up only if it holds a
   real crop. If `prev-1` is blank, `other` or `unsure`, do not look up. Say
   that rotation is not judged until the crop grown last is known.
2. Walk back from `prev-1` and stop at the first blank, `other` or `unsure`.
   Keep every crop between `prev-1` and that gap. Drop everything older than the
   gap. A gap in the middle of a history ends the history.
3. Keep a crop that repeats in the same history. The model assesses each
   adjacent pair, so `maize>maize` is a real path with a real answer: no rule is
   held for that pair. Do not remove the repeat.
4. Join the rest with `>`, newest last.

Step 2 matters as much as step 1. If a gap only drops the field and the join
closes over it, the key claims two crops were adjacent when a season sits
between them. For example, `prev-3` sorghum, `prev-2` blank, `prev-1` finger
millet would build `sorghum>finger_millet` and report one reason against. The
model is right about that pair, but it was not the pair that grew. Stop the walk
at the gap and only `finger_millet` is looked up.

Step 1 matters more than it looks. Without it, a blank newest field is dropped
and an older field takes the newest position. The shortened key is a real path,
so the lookup succeeds and returns a rotation verdict for a history that has no
crop grown last. Three such cases return a verdict: `sorghum` then
`finger_millet` reports one reason against, and two maize and common bean pairs
report one reason for. A user who leaves the newest field empty must not get a
warning about a crop they did not grow last.

## Order matters, and a wrong order does not fail

The three fields on the page are ordered newest first. The newest crop is
`prev-1`, labelled "This season follows". The oldest is `prev-3`. The key runs
the other way, oldest first and newest last.

A handler must reverse the field order, or build from the oldest kept crop to
`prev-1`.

The index cannot catch this. A reversed key is still a real crop path, so it
exists in the index and the lookup succeeds. It returns a different pairing with
no error. For example, `sorghum>finger_millet` reports
one reason against, and `finger_millet>sorghum` reports none. Both keys are
present. Only the first carries the warning that finger millet should not
follow sorghum.

So a lookup that succeeds is not proof that the order is right.

The index holds no empty-key entry and no key with an empty segment.

If the lookup finds no entry, the screen says no comparison is available for
that path. Do not invent a result and do not fall back to a shorter path. Use
that message for a real miss only. It must not absorb a reversed key.

`scripts/qa_path_index_check.py` checks the file against the live model.

## Example top-level skeleton

```json
{
  "schema_version": "1.0",
  "generated_utc": "2026-11-14T21:05:00Z",
  "data_status": { "site_climate": "ready", "crop_windows": "pending" },
  "meta": { "sources": [], "assumptions": [], "raw_cache_sha256": "...", "pipeline": "" },
  "site": { "name": "Soroti", "lat": 1.79, "lon": 33.5, "scale_note": "" },
  "period": { "start_date": "1991-01-01", "end_date": "2025-12-31", "n_years": 35 },
  "monthly_climatology": [],
  "annual": { "rain_mm_mean": 843.0, "rain_mm_median": 839.4, "n_years_complete": 35, "t2m_mean_c": 25.41 },
  "onset": { "definition": {}, "summary": [], "by_year": [] },
  "soil": { "ph_h2o": 6.12, "clay_pct": 40.73, "sand_pct": 38.87, "silt_pct": 20.32, "texture_sum_pct": 99.92 },
  "crops": [],
  "notes": []
}
```
