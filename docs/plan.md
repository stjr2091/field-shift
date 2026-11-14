# MVP plan to submission — locked Sat 14 Nov 2026, 16:30 EAT

One question: **what do I plant, and when.** One district, five crops (four if the sources fail), one thin app, one write-up. Nothing else gets built.

## What we ship, and what is actually true today

| Piece | Already true | Missing | Owner | By |
| --- | --- | --- | --- | --- |
| Five crops | Named below, all rain-fed Ugandan staples with documented planting windows | Nothing — call is made | Lead | done |
| Demo area | Nakasongola district, one point (1.35 N, 32.45 E); 2022 Rakai/Nakasongola trial is the local anchor | District outline for the map | Joel | Sun 09:00 |
| Rules table | Convention, schema and 4 checked sources | All rows. `rules.csv` has a header only | Lead | tonight 19:00 |
| Notebook | Repo layout, download script stub | Every cell. Data pull, onset logic, crop windows, outputs | Lead | tonight 22:30 |
| App | Thin-app rule agreed (reads precomputed JSON only) | One page, charts, deploy URL | Joel | tonight 22:30 |
| Write-up | Brief, sources file, AI-use register started | Draft, figures, citations, submission form | Marvin | Sun 12:00 |

## Calls I am making now (say so by 16:30 if you object)

- **Crops:** maize, common bean, finger millet, sorghum, groundnut. Two cereals, a legume, a pulse and a drought-tolerant small grain; all have extension guidance and all fit a one-season planting window.
- **Site:** Nakasongola, one point. NASA POWER is a ~50 km grid cell, so we say **district-scale**, never parcel-scale. That is a limit we state, not a problem we hide.
- **Data:** NASA POWER daily (rain, temperature, root-zone soil wetness) and SoilGrids static soil (pH, texture). Both free, no key, both checked answering today. One source each, no parallel ingests.
- **Cut list, frozen:** Landsat greenness, yield prediction, login/auth, a database, dashboards, extra districts, extra crops, any paid tool.

## Minimum rules table

Four rows per crop, 20 rows total: planting rainfall threshold, season length to maturity, soil pH range, temperature range. Every row carries `source` and `source_url`; `unknown` where none exists. **Only sourced rows reach the outputs, and any crop with fewer than three sourced rows is cut** — we submit four crops rather than publish a number we cannot defend.

## Notebook: four outputs, nothing else

1. `results/site_climate.json` — monthly rainfall climatology, onset date per season per year, dry-spell risk.
2. `results/crop_windows.csv` — per crop: documented current-practice window, the window our rules and rainfall support, and the gap between them.
3. `results/fig_*.png` — rainfall and soil charts, plus one district map.
4. `results/app_data.json` — the only file the app reads.

One assumption, stated once in the notebook and in the write-up: planting is possible when the crop's rainfall threshold is met over a rolling 10-day sum and root-zone wetness is at or above 0.40. It is an assumption, not a sourced rule.

## Checkpoints (EAT)

| Time | Must be true |
| --- | --- |
| Sat 16:30 | This plan agreed; rules skeleton and assignments out |
| Sat 19:00 | POWER extract runs end to end for one crop; 8+ sourced rules rows |
| Sat 22:30 | All crops through the notebook, JSON written, deploy URL live |
| Sun 09:00 | Write-up draft and figures in; first demo dry run |
| Sun 12:00 | Copy and figures frozen; submission form filled as a draft; bug fixes only |
| Sun 18:00 | **Freeze.** Repo tagged, URL opened on a phone, write-up final |
| Sun 21:00 | Submitted, three hours of buffer |

## First three assignments

1. **Lead (me):** the rules table, the POWER and SoilGrids extract, the notebook, review and merge. This is the critical path; everything else waits on the JSON.
2. **Joel:** the charts, the district map and the one-page Streamlit app that reads `app_data.json`, plus the deploy. Nothing computes in the app.
3. **Marvin:** the write-up, citations in `SOURCES.md`, AI-use rows, the submission form and the demo video if the official brief asks for one.

## What can still sink us

- **Rules sources are the only real risk.** If sorghum and groundnut have no usable sourced rows by 19:00, we ship three sourced crops plus two marked unknown, or four crops. No invented numbers.
- **The official brief is still unconfirmed** (board task is blocked on a third-party warning). Marvin confirms deliverables by 18:00; if the brief asks for something we have not built, we say what we cut.
- **Deploy needs a login.** Streamlit Community Cloud is free but the repo must be connected once under Stephen's GitHub. If that is a nuisance, the repo goes public and we ship a static page on GitHub Pages instead.
