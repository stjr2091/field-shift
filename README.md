# 🌱 AgriCloud

**Crop decisions grounded in rainfall, soil and traceable evidence.**

AgriCloud is an agricultural decision-support prototype for the **NASA Space Apps Challenge — Field Shift category**. It helps farmers explore which crops may suit a season, understand the evidence behind an option, and see what still needs checking before planting.

The project connects a reproducible Python analysis with a lightweight web app and recommendation service. The analysis produces the data the app uses, so an answer can be traced back to its source, method and assumptions.

[Quick start](#-quick-start) · [Reproduce the analysis](#-reproduce-the-analysis) · [Google Colab](#run-in-google-colab) · [API keys](#-optional-api-integrations) · [Sources](SOURCES.md) · [AI use](#-ai-use)

## What AgriCloud does

- Analyses historical rainfall, temperature and root-zone wetness alongside soil information.
- Compares sourced crop requirements and documented crop sequences.
- Presents a crop option, its seasonal window where supported, reasons and limitations.
- Separates seasonal suitability from readiness to plant.
- Provides a reproducible notebook, derived datasets and a rainfall climatology figure.
- Offers an English advice interface, with optional model-assisted phrasing and Luganda translation integrations.

The study site is **Soroti, Uganda**. The crop-history inputs cover maize, common bean, finger millet, sorghum and groundnut. The sourced-rule coverage determines which crops can be recommended; accepting a crop as history does not mean it is eligible as a recommendation.

> **Decision support, not a planting guarantee.** Historical suitability and forecast rainfall do not prove that a particular field is ready to plant. AgriCloud does not predict yield, harvest or income.

## 🧭 How it works

| Layer | What it does | Main files |
| --- | --- | --- |
| Data collection | Retrieves and caches NASA POWER and SoilGrids data. | [download_data.py](scripts/download_data.py), [SOURCES.md](SOURCES.md) |
| Reproducible analysis | Calculates climate summaries, seasonal onset indicators and soil summaries. | [field_shift.ipynb](notebooks/field_shift.ipynb), [field_shift_data.py](notebooks/field_shift_data.py) |
| Crop evidence | Holds sourced requirements and evaluates crop sequences. | [rules.csv](rules/rules.csv), [crop_path.py](notebooks/crop_path.py) |
| App-data build | Produces the derived datasets consumed by the interface and service. | [build_app_data.py](scripts/build_app_data.py), [build_path_index.py](scripts/build_path_index.py) |
| Recommendation service | Validates inputs and returns advice, evidence and limitations. | [server/](server/README.md) |
| Web interface | Collects inputs and displays advice and supporting details. | [app/](app/README.md) |

The historical climate record and near-term weather context serve different purposes. Unknown evidence stays unknown; it must not be presented as a measured benefit or a planting instruction.

## 🚀 Quick start

### Requirements

For the web app and recommendation service:

- Python **3.11 or later**.
- A modern browser.
- The committed derived files in `results/` and `app/app_data.json`.

The runtime service and static frontend use Python's standard library. The scientific dependencies are needed to regenerate the analysis, not merely to open the sample app.

### 1. Try the sample interface

Open a terminal in the project root:

```bash
python -m http.server 8000 --bind 127.0.0.1
```

Open [AgriCloud sample mode](http://127.0.0.1:8000/app/index.html?api=mock).

Sample mode uses fixed examples. It does not recalculate advice from every submitted value and does not require API keys.

### 2. Run the recommendation service

Keep the static server running. In a second terminal, from the same project root:

```bash
python server/app.py
```

Open [AgriCloud with the local API](http://127.0.0.1:8000/app/index.html?api=http://127.0.0.1:8099/recommend).

The default API address is `http://127.0.0.1:8099`. The `HOST` and `PORT` environment variables configure the service. Use an available port if either example port is occupied, and update the URL to match.

The advice service can return a plain English card without Groq or Sunbird credentials. External integrations are optional; see [API integrations](#-optional-api-integrations).

## 🔬 Reproduce the analysis

### Install the scientific dependencies

Create an isolated environment from the project root:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

```bash
source .venv/bin/activate
```

Install the pinned project dependencies:

```bash
python -m pip install -r requirements.txt
```

[requirements.txt](requirements.txt) is the authoritative version list. Scientific package availability depends on the Python version and platform; the minimal app runtime and the full scientific environment have different requirements.

| Dependency group | Packages | Purpose |
| --- | --- | --- |
| Data and figures | pandas, NumPy, Matplotlib | Data processing, analysis and plots. |
| Notebook tooling | nbformat, nbclient, ipykernel | Notebook generation and execution. |
| Geospatial and visualisation packages | xarray, GeoPandas, Rasterio, Plotly | Included in the project environment for geospatial and visualisation work; not all are imported by the core data layer. |

### Download the source data

```bash
python scripts/download_data.py
```

This downloads missing inputs into `data/raw/`. NASA POWER and SoilGrids do not require Groq or Sunbird keys. Downloading requires an internet connection.

Raw downloads are not committed. A committed SoilGrids fallback is available in `data/processed/`; provenance and data-quality notes are documented in [SOURCES.md](SOURCES.md).

To deliberately refresh all downloads:

```bash
python scripts/download_data.py --force
```

### Run the notebook locally

Open [notebooks/field_shift.ipynb](notebooks/field_shift.ipynb) in a notebook environment such as Jupyter or VS Code, select the Python environment containing the dependencies, and run all cells from top to bottom. Keep the complete project folder alongside the notebook: it imports local Python modules and reads the rules and data directories.

The equivalent climate-analysis script can be run without a notebook interface:

```bash
python notebooks/field_shift_data.py
```

Then build the app datasets:

```bash
python scripts/build_app_data.py
python scripts/build_path_index.py
```

### Run in Google Colab

Use the complete project, not only the notebook file. One portable approach is to upload a project ZIP:

1. Create `agricloud.zip` with `requirements.txt`, `notebooks/`, `scripts/`, `rules/` and the other project folders at the archive root. Exclude credentials, virtual environments and local runtime configuration.
2. In a Colab notebook, upload that ZIP using the **Files** panel.
3. Run this setup cell:

```python
!unzip -q /content/agricloud.zip -d /content/agricloud
%cd /content/agricloud
%pip install -r requirements.txt
```

4. Run the data download and execute the project notebook in a second cell:

```python
import sys
import subprocess
from pathlib import Path

import nbformat
from nbclient import NotebookClient

subprocess.run([sys.executable, "scripts/download_data.py"], check=True)

path = Path("notebooks/field_shift.ipynb")
notebook = nbformat.read(path, as_version=4)
NotebookClient(
    notebook,
    timeout=600,
    kernel_name="python3",
    resources={"metadata": {"path": str(Path.cwd())}},
).execute()
nbformat.write(notebook, "notebooks/field_shift.executed.ipynb")

subprocess.run([sys.executable, "scripts/build_app_data.py"], check=True)
subprocess.run([sys.executable, "scripts/build_path_index.py"], check=True)
```

The executed notebook and regenerated files remain in the Colab session. Download the outputs before ending the session. If the current Colab Python runtime cannot install the pinned dependencies, use a compatible local environment; do not silently substitute package versions when comparing reproducibility.

### Generated outputs

| Output | Contents |
| --- | --- |
| [results/site_climate.json](results/site_climate.json) | Site climate summary, analysis assumptions, provenance and data quality. |
| [results/fig_monthly_rain_climatology.png](results/fig_monthly_rain_climatology.png) | Monthly rainfall climatology figure. |
| [results/app_data.json](results/app_data.json) | Derived crop and seasonal data used downstream. |
| [results/path_index.json](results/path_index.json) | Precomputed crop-path index. |
| [app/app_data.json](app/app_data.json) | App-local copy of the derived data. |

For the analytical approach, read [Method](docs/method.md), [Crop rules](docs/crop_rules.md) and the [Technical write-up](docs/writeup.md).

## 🔑 Optional API integrations

The climate-analysis pipeline does not require these credentials. They enable optional hosted services in the recommendation layer.

| Variable | Provider | Purpose | Without it |
| --- | --- | --- | --- |
| `GROQ_API_KEY` | Groq | Phrases supplied facts into an advice card. | The service uses the plain English template. |
| `SUNBIRD_API_TOKEN` | Sunbird | Supports English-to-Luganda translation. | Translation is unavailable; English advice remains available. |

Obtain credentials from the respective providers and supply them through the **backend process environment** or the deployment platform's secret settings. Never add key values to source files, browser JavaScript, sample JSON, notebooks or a public repository.

Credentials are not a substitute for provider opt-in and request-budget configuration. Consult the [service documentation](server/README.md) before enabling external calls. Translation availability depends on provider access, limits and configured safeguards. The presence of a key does not establish translation accuracy.

Generated wording must stay within the supplied evidence. A rejected draft falls back to the plain card. Language output requires meaning checks; synthetic interface fixtures do not demonstrate actual Luganda quality.

## ✅ Check the data and service

After downloading the raw inputs and rebuilding the datasets:

```bash
python scripts/qa_onset_check.py
python scripts/qa_path_check.py
python scripts/qa_path_index_check.py
```

The onset check needs the raw NASA POWER file. The path checks need the derived outputs. A runtime demonstration using committed results does not reproduce the analysis by itself.

For the recommendation checks:

```bash
python server/test_recommend.py
```

Keep automated checks offline with provider calls mocked or disabled. Do not use production credentials for repeated test runs.

## 📁 Project structure

```text
app/          Browser interface and sample responses
data/         Raw download cache and processed fallback data
docs/         Method, data schema, crop rules and technical write-up
notebooks/    Reproducible notebook and analysis/model modules
results/      Derived JSON datasets and generated figures
rules/        Sourced crop-requirement table
scripts/      Download, build, notebook-generation and QA utilities
server/       Recommendation service and card/translation safeguards
AI_USE.md     Record of AI assistance
SOURCES.md    Data sources, provenance and quality notes
requirements.txt
LICENSE
```

## Data credits and limitations

Climate data comes from **NASA POWER**, including MERRA-2-derived precipitation, temperature and root-zone wetness. Soil information comes from **ISRIC SoilGrids**. Exact queries, provenance, quality notes and source limitations are recorded in [SOURCES.md](SOURCES.md).

- Climate evidence is district-scale, not a measurement of an individual field.
- Missing crop requirements and unsupported rotation pairs remain explicit unknowns.
- A historical seasonal window is not a confirmed sowing date.
- Short-term weather is context, not proof that planting is safe.
- The prototype does not estimate yield, income or guaranteed agricultural outcomes.

## 🤖 AI use

AI coding assistance supported the application's development, data-analysis implementation, documentation and checks. The [AI-use record](AI_USE.md) describes the assistance used.

At runtime, optional AI-assisted phrasing uses facts supplied by the recommendation service; crop requirements and numerical evidence come from the rules and cited data sources. AI-generated text is not an independent agronomic source, and a generated translation is not evidence of linguistic correctness.

## License

AgriCloud is released under the **Apache License 2.0**. See [LICENSE](LICENSE).
