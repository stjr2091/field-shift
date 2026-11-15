# Late Rains, Next Crop (Field Shift)

NASA Space Apps 2026, Field Shift challenge, team AgriCloud.
Submission deadline: Sunday 15 Nov 2026, 23:59 EAT.

## The one question

What do I plant, and when. No yield prediction.

The MVP reads rainfall and soil together for about five candidate crops with sourced requirements, then compares documented current practice against other sequences and planting windows under the same assumptions.

## Outputs

- A reproducible notebook (runs on Colab or Kaggle)
- Maps, graphs and tables
- A thin webapp that shows precomputed results only
- A technical write-up

Landsat greenness is parked for now.

## Open items

- The five candidate crops
- The demo area
- The rules table content. Sources checked so far: MAAIF maize manual, MAAIF beans manual, a finger millet report, a 2022 Rakai/Nakasongola planting-date trial. Where a rule has no source, mark it unknown.
- Owners for the data and rules areas (Joel: visualisation and demo, Marvin: communication)

## Stack (starting suggestion)

Python notebooks on Colab or Kaggle; pandas and xarray for data; geopandas and rasterio for maps; matplotlib or plotly for graphs; a thin webapp that only reads precomputed outputs; rules as a plain CSV with a source column on every row; one pinned requirements file.

## Repo layout

- `data/raw` - raw downloads, kept out of git (see `scripts/download_data.py`)
- `data/processed` - cleaned outputs of notebooks
- `notebooks` - analysis, reproducible top to bottom
- `rules` - rules CSV, one source per row
- `results` - the four published outputs (`site_climate.json`, `crop_windows.csv`, `fig_*.png`, `app_data.json`), committed so the app and the write-up read them
- `app` - thin webapp over precomputed results
- `docs` - write-up and the standing brief

## Running the data layer

```bash
pip install -r requirements.txt
python scripts/download_data.py        # POWER + SoilGrids into data/raw (no key)
python notebooks/field_shift_data.py   # rebuild results/site_climate.json
```

`notebooks/field_shift.ipynb` is the readable version of the same steps and runs
top to bottom after the download. The app contract for `results/app_data.json`
is `docs/app_data_schema.md`.

## AI contribution

An automated coding assistant helped write and check the code, the data analysis and the documentation in this repository. The project owner reviewed and merged every change. The assistant made no agricultural claim. All crops, thresholds, planting windows and reasons come from the cited sources and the rules table. Per-use detail is in `AI_USE.md`.

## Workflow

main is protected; work goes on short branches; one review before merge. A sources file and AI-use credits are kept from day one.

These rules are the starting suggestions. The team's baseline rules win wherever they differ; they get settled on a call, and planning stays with Stephen.
