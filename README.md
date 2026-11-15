# Field Shift

Field Shift helps an extension worker and a farmer decide what to plant and when. It compares the crops a farmer has grown with other options for their district, using NASA POWER rainfall, SoilGrids soil data and a crop rules table where every rule has a source. It explains the reasons in plain words.

This version covers one district, Soroti, with maize, beans and millet.

## Setup

Tested on Python 3.14 (Linux). The pinned versions need Python 3.12 or newer, because numpy 2.5.4 requires it.

```bash
git clone https://github.com/stjr2091/field-shift.git
cd field-shift
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Dependencies

All pinned in requirements.txt:

- pandas 2.3.3
- numpy 2.5.4
- matplotlib 3.10.6
- notebook tooling for step 5: nbformat 5.10.4, nbclient 0.10.2, ipykernel 6.30.1
- nothing extra for server/ and app/: both use only the Python standard library
- also pinned for later map work, imported nowhere yet: xarray 2026.9.0, geopandas 1.2.0, rasterio 1.5.2, plotly 7.1.0

No API keys or accounts are needed.

## How to run

The files in results/ are already committed, so you can go straight to step 5 to look around. Steps 1 to 4 rebuild everything from scratch.

1. Get the raw data. `data/raw` is not in git, so this always comes first:

   ```bash
   python scripts/download_data.py
   ```

   It pulls NASA POWER and SoilGrids into `data/raw`.

2. Build the site climate (writes `results/site_climate.json`):

   ```bash
   python notebooks/field_shift_data.py
   ```

3. Build the crop path index and the app data:

   ```bash
   python scripts/build_path_index.py
   python scripts/build_app_data.py
   ```

4. Run the QA checks:

   ```bash
   python scripts/qa_onset_check.py
   python scripts/qa_path_check.py
   python scripts/qa_path_index_check.py
   ```

5. Read the analysis in `notebooks/field_shift.ipynb`. To regenerate it:

   ```bash
   python scripts/make_notebook.py
   ```

6. Start the backend:

   ```bash
   python server/app.py
   ```

   It serves on http://127.0.0.1:8099 (`PORT=...` to change). Its tests are in `server/test_recommend.py`.

7. Open the app:

   ```bash
   python -m http.server 8000 --directory app
   ```

   Then go to http://localhost:8000

## Repo map

- `notebooks/`: the readable analysis (`field_shift.ipynb`), the script that builds the site climate (`field_shift_data.py`) and `crop_path.py`
- `scripts/`: data download, the build scripts and the QA checks
- `data/`: `raw/` (downloaded, not in git) and `processed/`
- `rules/rules.csv`: the crop rules, with a source for every row. Rows with no source are marked unknown
- `results/`: the computed outputs the app reads (`site_climate.json`, `path_index.json`, `app_data.json`) and the rainfall figure
- `app/`: a thin web app over the precomputed results (`index.html`, `app.js`, `styles.css`, `app_data.json`)
- `server/`: the backend (`app.py`, `card.py`, `recommend.py`) and its tests
- `docs/`: brief, plan, method, write-up, crop rules and the app data schema

## Data credits

Climate data: NASA POWER (MERRA-2) daily point API, agroclimatology community. Soil data: ISRIC SoilGrids v2.0 point query. Both are free and keyless. Exact URLs, parameters, access dates and quality notes are recorded in `SOURCES.md` and in the provenance block inside `results/site_climate.json`.

## AI use

An automated coding assistant helped write and check the code, the data analysis and the documentation in this repository. The work was reviewed before release. The assistant made no agricultural claim: crops, thresholds, planting windows and reasons come from the rules table and the cited sources, including rows marked as team expertise or prototype assumptions. Per-use detail is in `AI_USE.md`.

## License

Apache License 2.0. See `LICENSE`.

*This is a prototype. Its advice is not proof.*
