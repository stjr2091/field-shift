# Late Rains, Next Crop (Field Shift)

Field Shift answers one question for a farmer going into a season: what do I plant, and when. It reads rainfall and soil records for a site, compares them with the documented requirements of candidate crops, and then compares documented current practice with other crop sequences and planting windows under the same assumptions.

It is a decision-support prototype built for the NASA Space Apps 2026 Field Shift challenge. It is not a yield prediction: no yield, harvest or income figure is held.

## Setup

Tested on Python 3.14 (Linux). The pinned versions need Python 3.12 or newer, because numpy 2.5.4 does; on an older Python pip refuses the install with "No matching distribution found for numpy==2.5.4". Then:

```bash
pip install -r requirements.txt
```

## Dependencies

One pinned requirements file:

- Data layer: `pandas==2.3.3`, `numpy==2.5.4`, `matplotlib==3.10.6`
- Notebook execution and regeneration: `nbformat==5.10.4`, `nbclient==0.10.2`, `ipykernel==6.30.1`
- Reserved for the later map and app steps, not imported by the data layer: `xarray==2026.9.0`, `geopandas==1.2.0`, `rasterio==1.5.2`, `plotly==7.1.0`

## Running it

The download comes first, because raw data is not in git.

```bash
# 1. Raw data: NASA POWER daily point data and a SoilGrids point extract, both free and keyless
python scripts/download_data.py          # fetches anything missing into data/raw/
python scripts/download_data.py --force  # refetch everything

# 2. Notebook: runs top to bottom and writes results/site_climate.json plus the climatology figure
#    open notebooks/field_shift.ipynb in a notebook environment (Jupyter, Colab or Kaggle);
#    the standalone equivalent of the same steps:
python notebooks/field_shift_data.py

# 3. Build the app data
python scripts/build_app_data.py         # writes results/app_data.json and results/path_index.json,
                                         # and mirrors app_data.json into app/
python scripts/build_path_index.py       # standalone rebuild of the path index alone
python scripts/make_notebook.py          # regenerates the notebook file from its cell list

# 4. QA checks
python scripts/qa_onset_check.py         # re-derives every onset date from the raw POWER file
python scripts/qa_path_check.py          # the ordered-path model, and notebook/build agreement
python scripts/qa_path_index_check.py    # the path index against the live model

# 5. App: static page, no build step, no dependencies
python3 -m http.server 8000              # then open http://localhost:8000/app/index.html

# 6. Advice service
python server/app.py                     # serves on http://127.0.0.1:8099 (PORT=... to change)
python server/test_recommend.py          # the service checks, no network needed
```

`scripts/qa_path_check.py` and `scripts/qa_path_index_check.py` expect the built results in place, so run the build step first. Optional environment variables for the service's card and translation steps are documented in `server/README.md`; without them the service answers with the plain card.

These steps were run in order from a clean clone on Python 3.14 (Linux) on 15 Nov 2026. Every command completed, the QA checks and the service checks passed, and the regenerated files in `results/` matched the committed ones apart from the build timestamp each file carries.

## Repository map

- `notebooks/` — the reproducible analysis: `field_shift.ipynb` (top to bottom), its data layer (`field_shift_data.py`) and the ordered-path model (`crop_path.py`)
- `scripts/` — the data download, the result builders, the notebook generator and the QA checks
- `data/` — raw downloads land in `data/raw/` and never enter git; the committed SoilGrids fallback lives in `data/processed/` so the pipeline reproduces without the live service
- `rules/rules.csv` — the crop rules table, one source per row; a rule without a source is marked unknown, never guessed
- `results/` — the committed outputs everything downstream reads: `site_climate.json`, `app_data.json`, `path_index.json` and the monthly rainfall climatology figure
- `app/` — the thin web app over precomputed results, one form and one advice card
- `server/` — the advice service, answering from the files the notebook and build steps write
- `docs/` — method and plan notes, the app-data schema, QA records and the technical write-up

## Data credits

Climate data: NASA POWER (MERRA-2) daily point API, agroclimatology community. Soil data: ISRIC SoilGrids v2.0 point query. Both are free and keyless. Exact URLs, parameters, access dates and quality notes are recorded in `SOURCES.md` and in the provenance block inside `results/site_climate.json`.

## AI use

An automated coding assistant helped write and check the code, the data analysis and the documentation in this repository. The work was reviewed before release. The assistant made no agricultural claim: crops, thresholds, planting windows and reasons come from the rules table and the cited sources, including rows marked as team expertise or prototype assumptions. Per-use detail is in `AI_USE.md`.

## License

Released under the Apache License 2.0. See `LICENSE`.

*The prototype's advice is not proof.*
