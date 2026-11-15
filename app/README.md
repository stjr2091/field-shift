# App

A thin webapp that only reads precomputed outputs (maps, graphs, tables). It does no
computation when a page is opened. The framework is open.

## How to open it

Serve the repository root. Do not serve this folder.

The page reads its data from `results/app_data.json`, one level up. If this folder is
the web root, the data request fails and the page shows nothing.

From the repository root:

    python3 -m http.server 8000

Then open http://localhost:8000/app/index.html

The data file is built by `scripts/build_app_data.py`. It reads `results/site_climate.json`
and `rules/rules.csv`. While `rules/rules.csv` holds no sourced crop rows, the page shows
the rain and soil panels and a waiting state for crops.
