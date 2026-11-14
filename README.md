successfully downloaded text file (SHA: 587e03b079a96db189d7e3075c6bf936066a63b3)
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
- `app` - thin webapp over precomputed results
- `docs` - write-up and the standing brief

## Workflow

main is protected; work goes on short branches; one review before merge. A sources file and AI-use credits are kept from day one.

These rules are the starting suggestions. The team's baseline rules win wherever they differ; they get settled on a call, and planning stays with Stephen.

## Credits

Repository setup was done with help from AI agents (Openbot).
