"""Generate notebooks/field_shift.ipynb from a cell list, so the notebook file is
valid JSON and stays reviewable in this repo. Run:

    python scripts/make_notebook.py
"""

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "field_shift.ipynb"

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

CELLS = [
    md(
        """# Field Shift — site climate for Soroti

One notebook for one question: **what do I plant, and when**, for Soroti
district (1.79 N, 33.50 E).

This file is the data layer. It pulls NASA POWER daily data and a SoilGrids
point extract, builds the monthly rainfall climatology, detects a planting onset
per season per year, and writes **`results/site_climate.json`** plus one figure.
Crop windows and `app_data.json` come in later cells as the rules table lands.

Run top to bottom. On a clean runtime the first code cell downloads the raw
cache; everything after that works offline.

**One assumption, stated once:** planting is possible when a crop's rainfall
threshold is met over a rolling 10-day sum and root-zone wetness (GWETROOT) is
at or above 0.40. It is our assumption, not a sourced agronomic rule. Until
`rules/rules.csv` has crop thresholds, the site screens at 20 mm per 10 days and
the sensitivity to 15 and 25 mm is reported next to it.
"""
    ),
    code(
        """import sys
from pathlib import Path

import pandas as pd

NOTEBOOKS = Path.cwd()
if (NOTEBOOKS / "field_shift_data.py").exists():
    sys.path.insert(0, str(NOTEBOOKS))
    ROOT = NOTEBOOKS.parent
else:  # run from the repo root
    sys.path.insert(0, str(NOTEBOOKS / "notebooks"))
    ROOT = NOTEBOOKS

import field_shift_data as fs

pd.set_option("display.width", 120)
print("repo root:", ROOT)
print("site:", fs.SITE_NAME, fs.LAT, "N", fs.LON, "E", "| period:", fs.START, "to", fs.END)"""
    ),
    md("## 1. Raw data\n\nPOWER daily point data and the SoilGrids extract, cached in `data/raw/` (not in git)."),
    code(
        """sys.path.insert(0, str(ROOT / "scripts"))
import download_data

download_data.get_power(force=False)
download_data.get_soilgrids(force=False)"""
    ),
    md(
        """## 2. Load and check

`-999` is POWER's missing-data sentinel and is converted to NaN, then counted.
Missing days, duplicates and leftover NaNs are reported rather than filled."""
    ),
    code(
        """power = fs.read_power_csv()
daily = power.daily
print(f"rows: {len(daily)}  {daily.index.min().date()} to {daily.index.max().date()}")
display(pd.DataFrame([power.quality]).T.rename(columns={0: "value"}))
display(daily.describe().T)"""
    ),
    md("## 3. Monthly rainfall climatology\n\nWhole calendar months only: a month counts when every day is present and no rain value is missing."),
    code(
        """totals = fs.monthly_total_series(daily)
monthly, annual = fs.monthly_climatology(totals)
display(pd.DataFrame(monthly).set_index("month"))
print("annual:")
display(pd.Series(annual))"""
    ),
    code(
        """fig_path = fs.plot_monthly_climatology(monthly)
print("wrote", fig_path.relative_to(ROOT))"""
    ),
    md(
        """## 4. Onset per season per year

Onset is the first day the trailing 10-day rain sum crosses the threshold while
GWETROOT is at or above 0.40, **and** the previous 10-day sum was below it. The
crossing condition is what stops a search window that opens mid-season from
returning the window's first day every year.

Note the soil gate: GWETROOT never dropped below 0.40 in this record, so at this
site the soil condition never binds and onset is decided by rainfall alone."""
    ),
    code(
        """onsets = fs.onset_table(daily)
onset_df = pd.DataFrame(onsets)
display(onset_df.pivot(index="year", columns="season", values="onset_date").tail(10))
display(pd.DataFrame(fs.onset_summary(onsets, daily)).set_index("season"))"""
    ),
    md("## 5. Soil at the point (SoilGrids, 0–30 cm depth-weighted)"),
    code(
        """soil = fs.read_soilgrids()
display(pd.Series(soil["summary_0_30cm"]))
print("texture sum (%):", soil["texture_sum_pct"], "| source file:", soil["source_file"])"""
    ),
    md("## 6. Write the output\n\nThe JSON carries its own provenance: source URLs, the raw-file SHA-256, the assumption list, and the data-quality counts."),
    code(
        """payload = fs.build_site_climate()
out = fs.write_outputs(payload)
print("wrote", out.relative_to(ROOT))
print("sha256 of raw cache:", payload["meta"]["raw_cache"]["sha256"])
print("bytes:", out.stat().st_size)"""
    ),
]

nb = nbf.v4.new_notebook(cells=CELLS)
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nb.metadata["language_info"] = {"name": "python"}
OUT.write_text(nbf.writes(nb), encoding="utf-8")
print("wrote", OUT.relative_to(ROOT))
