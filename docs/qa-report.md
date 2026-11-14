# Field Shift — independent QA report (first pass)

Audit date: **2026-11-14**, first pass due 23:00 EAT.
Auditor: Evidence QA. Artefacts audited, not edited.

Commits in scope:

| Branch | Commit | What it holds |
| --- | --- | --- |
| `main` | `e72aec5` | scaffold only; no notebook, no rules rows, no `docs/plan.md` |
| `plan/mvp-scope` | `b9cc678` | `docs/plan.md` only |
| `feat/notebook-data` | `4cd3caf` | data layer, notebook, `site_climate.json`, app schema |

Verdict scale: **verified**, **weak**, **unsourced**, **invented**. No praise, no rewrite.

## 1. What was checked

- Read `docs/plan.md` (on `plan/mvp-scope`), `rules/rules.csv`, `notebooks/`, `SOURCES.md`, `AI_USE.md`, `docs/app_data_schema.md`, `README.md`.
- Ran `notebooks/field_shift.ipynb` top to bottom on Python 3.14.4 with the pinned versions (`pandas 2.3.3`, `numpy 2.5.4`, `matplotlib 3.10.6`, `nbclient 0.10.2`). All 15 cells completed, no errors.
- Re-ran with a fresh `data/raw` POWER cache; the live POWER URL returned HTTP 200 and **byte-identical** CSV (`sha256 ff9cec9c…0483`, 325,436 bytes).
- Recomputing was done with a separate stdlib-only script, not the team's `field_shift_data.py`.
- Compared the notebook's written `results/site_climate.json` with the committed one; compared the figure bytes.
- Checked both data URLs resolve (POWER 200, SoilGrids 200).

## 2. Verdict table

| # | Claim or artefact | Where | Verdict | Check | Severity | Owner | Exact fix |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 20 sourced crop rules (4 per crop × 5 crops) exist | `rules/rules.csv` | **unsourced** | File is header only in every branch: 0 of 20 rows. Nothing downstream can cite a crop rule. | blocker | Lead | Add the 20 rows with `crop,stage,parameter,value_min,value_max,unit,window,source,source_url,notes`; mark `unknown` where no source; cut any crop with fewer than 3 sourced rows. |
| 2 | Notebook writes `results/app_data.json` | plan §Notebook output 4; `docs/app_data_schema.md` | **unsourced** | File does not exist, and no notebook cell or function writes it. The notebook writes only `site_climate.json` and one figure. | blocker | Notebook Engineer / Lead | Add the cell that writes `results/app_data.json` to schema 1.0; until rules land write `crops: []` and `data_status.crop_windows: "pending"`; commit the file. |
| 3 | Rule sources are citable | `SOURCES.md` | **unsourced** | MAAIF maize, MAAIF beans, finger millet report and the 2022 Rakai/Nakasongola trial are named but have no publisher, year, URL or access date. Two entries literally say "full citation to add". | blocker | Marvin | Replace each with publisher, title, year, URL, access date; if a source cannot be produced, mark it `unknown` and remove the crop claim that depends on it. |
| 4 | Notebook produces four published outputs | `docs/plan.md`; `results/` | **unsourced** | Only 1 of 4 exists: `site_climate.json`. Missing `crop_windows.csv`, the soil chart, the district map, and `app_data.json`. | major | Lead (data); Joel (map/charts) | Add `results/crop_windows.csv` (documented window, supported window, signed gap), a soil figure, and the district map; commit them. |
| 5 | Write-up exists and its claims can be audited | plan §What we ship | **unsourced** | No write-up in `docs/`; only `brief.md` and `app_data_schema.md`. | major | Marvin | Commit the write-up; then every number in it gets one row in this table. |
| 6 | Thin app reads precomputed JSON and is deployed | plan §What we ship; `app/` | **unsourced** | `app/` contains only a 129-byte README. No page, no deploy URL. | major | Joel | Commit the one-page app that reads `app_data.json` only; record the public URL in `README.md` and on the workboard. |
| 7 | Submission artefacts ship together | branches | **weak** | `docs/plan.md` is only on `plan/mvp-scope`; the notebook is only on `feat/notebook-data`; `main` has neither. Nothing is merged. | major | Lead | Merge `plan/mvp-scope`, then `feat/notebook-data`, into `main` (or rebase both); tag the freeze commit. |
| 8 | "Onset date" means the day the rains start | notebook §4; JSON `onset_date` | **weak** | `onset_date` is the **last day of the 10-day window that first reaches 20 mm**, not the first rain day. It can lag first rain by up to 9 days. The code and definition are consistent; the plain-English reading is not. | major | Lead / Marvin | In notebook, write-up and app label, call it "day the 10-day rainfall threshold is first met"; state the up-to-9-day lag; do not call it the first rain day. |
| 9 | Committed SoilGrids extract carries its URL and access date | `SOURCES.md` | **weak** | `data/processed/soilgrids_site.json` has keys `type, geometry, properties, query_time_s` only. No URL, no access date. The claim is false as written. | major | Lead | Add `url` and `accessed` to the committed extract (and the raw copy), or correct `SOURCES.md` to say only `query_time_s` is stored. |
| 10 | AI-use register is complete | `AI_USE.md` | **weak** | One row only (repo scaffold by Fo). It does not record AI use for the data layer, notebook, app schema or this QA run, though its own rule is "one row per use". Authorship cannot be verified from the repo. | major | Marvin | Add one row per AI-assisted artefact with date, tool, use and person; Lead confirms who wrote what. |
| 11 | POWER grid cell is "roughly 50 km" | `SOURCES.md`; `docs/plan.md` | **weak** | At 1.35° N, 0.5° lat ≈ 55.5 km and 0.625° lon ≈ 69.5 km. "~50 km" understates the cell; the district-scale caveat itself is correct. | minor | Marvin / Lead | Change to "~55 × 70 km (0.5° × 0.625° at this latitude)". |
| 12 | SoilGrids live query "takes about 30 s" | `SOURCES.md` | **weak** | Measured 12.8 s on 2026-11-14. Timing varies, but the stated figure is not what was seen. | minor | Lead | Say "typically 10–30 s" or drop the timing. |

## 3. Verified numbers (independent recompute)

Script: `/tmp/qa_recompute.py`, stdlib `csv`/`statistics` only, reading
`data/raw/power_daily_1.35N_32.45E_1991-2025.csv` directly. Percentiles use
linear interpolation to match the notebook.

| Published value | Published | Independent | Verdict |
| --- | --- | --- | --- |
| Days in period | 12,784 | 12,784 | verified |
| Missing days | 0 | 0 | verified |
| Duplicate dates | 0 | 0 | verified |
| `-999` sentinels | 0 | 0 | verified |
| Annual rainfall mean | 1114.4 mm | 1114.39 mm | verified |
| Annual rainfall median | 1074.8 mm | 1074.80 mm | verified |
| Annual min / max | 650.8 / 1595.5 mm | 650.8 / 1595.5 mm | verified |
| October rainfall mean | 147.7 mm | 147.66 mm | verified |
| First-rains onset median / p25 / p75 | 53.0 / 41.5 / 73.5 DOY | 53.0 / 41.5 / 73.5 | verified |
| Second-rains onset median / p25 / p75 | 219.0 / 214.0 / 231.0 DOY | 219.0 / 214.0 / 231.0 | verified |
| GWETROOT days below 0.40 | 0 | 0 (min 0.44) | verified |
| Soil pH 0–30 cm | 6.12 | 6.12 | verified |
| Soil clay / sand / silt | 38.57 / 39.63 / 21.80 % | 38.57 / 39.63 / 21.80 | verified |
| Texture sum | 100.0 % | 100.0 | verified |

No invented number was found in `results/site_climate.json`.

## 4. Notebook and output reproduction

| Check | Result | Verdict |
| --- | --- | --- |
| Runs top to bottom, clean kernel | 15/15 cells, no errors | verified |
| Re-run from repo root and from `notebooks/` | both paths work | verified |
| `results/site_climate.json` matches notebook output | identical apart from `meta.generated_utc` | verified |
| Figure matches | byte-identical SHA-256 | verified |
| `results/app_data.json` matches notebook output | file absent; notebook never writes it | **cannot check** |
| Live POWER URL | HTTP 200, identical 325,436 bytes | verified |
| Live SoilGrids URL | HTTP 200, 4 layers returned | verified |
| Pinned requirements resolve | exact versions confirmed in isolated target install | verified |
| Runs on Colab/Kaggle | not executed there | **unverified** |

## 5. Rules audit

No rules row exists, so there is no row-by-row source verdict to give. The four
named-but-uncited sources cannot be checked for value, unit, window, crop or
stage until they are cited. This is the largest evidence gap in the submission.

Cannot yet be checked:

- Whether MAAIF maize/beans manuals state the thresholds, season lengths, pH or temperature ranges later put in `rules.csv`.
- Whether the finger millet report exists and supports its rows.
- Whether the 2022 Rakai/Nakasongola trial exists, and what it measured.
- Whether `crop_windows.csv` gaps are computed from those rules.
- Whether the app's `crops[]` statuses (`sourced` / `partial`) match the rules.

## 6. Sources and AI-use completeness

- `SOURCES.md` is complete and precise for the two climate datasets (URL, parameters, period, units, sentinel handling, cache SHA). Verified.
- It is incomplete for all four rule sources (no citations).
- It overstates the committed SoilGrids extract (URL/access date not stored).
- `AI_USE.md` records one use; the register's own rule is one row per use. Incomplete.

## 7. What cannot be checked yet

- Every crop claim, because `rules.csv` is empty.
- `app_data.json`, because no file and no writer exist.
- The write-up's numbers, because no write-up exists.
- The district map and soil chart, because they do not exist.
- The deploy URL and app behaviour, because no app page exists.
- Colab/Kaggle execution; only this Linux/Python 3.14 run was checked.
- The official challenge brief; the workboard records it as blocked by a third-party warning.

## 8. Files and temporary work

This report is the only file added to the repo by this audit. The audited
artefacts were not edited. Temporary files created outside the repo:
`/tmp/qa_recompute.py`, `/tmp/qa_power_live.csv`, `/tmp/qa_soil_live.json`,
`/tmp/committed_site_climate.json`, `/tmp/committed_fig.png`, `/tmp/fsdeps`.
