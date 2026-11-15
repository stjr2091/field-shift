"""Download the raw data this project needs into data/raw/.

Raw data never lives in git (.gitignore keeps data/raw out). Run this once on a
clean runtime, then notebooks/field_shift.ipynb runs offline against the cache.

    python scripts/download_data.py            # fetch anything missing
    python scripts/download_data.py --force    # refetch everything

Two datasets, both free and keyless:

1. NASA POWER daily point data for the Soroti site point (1.79 N, 33.50 E),
   parameters PRECTOTCORR, T2M, GWETROOT, community AG, 1991-01-01..2025-12-31.
   POWER gives one grid cell (0.5 x 0.625 deg), so every number it produces is
   district-scale, never parcel-scale.

2. SoilGrids v2.0 site extract for the same point: pH and texture (clay, sand,
   silt) at 0-5, 5-15 and 15-30 cm, mean and median. SoilGrids is a 250 m
   product; the extract is a single-point query, cached because the service is
   slow (~30 s) and occasionally rate-limited.

Writes:
  data/raw/power_daily_1.79N_33.50E_1991-2025.csv
  data/raw/soilgrids_point_1.79N_33.50E.json

Neither file is committed. The SoilGrids extract is *also* copied to
data/processed/soilgrids_site.json, which IS committed, so the pipeline still
reproduces if SoilGrids is down. See SOURCES.md for the exact URLs.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

# --- Site -------------------------------------------------------------------
LAT = 1.79
LON = 33.50
SITE_NAME = "Soroti"

# --- NASA POWER -------------------------------------------------------------
POWER_START = "19910101"
POWER_END = "20251231"
POWER_PARAMS = ["PRECTOTCORR", "T2M", "GWETROOT"]
POWER_COMMUNITY = "AG"
POWER_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
    f"?parameters={','.join(POWER_PARAMS)}"
    f"&community={POWER_COMMUNITY}"
    f"&longitude={LON}&latitude={LAT}"
    f"&start={POWER_START}&end={POWER_END}"
    "&format=CSV"
)
POWER_PATH = RAW / f"power_daily_{LAT:.2f}N_{LON:.2f}E_1991-2025.csv"

# --- SoilGrids --------------------------------------------------------------
SOIL_PROPERTIES = ["phh2o", "clay", "sand", "silt"]
SOIL_DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]
SOIL_VALUES = ["mean", "Q0.5"]
SOIL_URL = (
    "https://rest.isric.org/soilgrids/v2.0/properties/query"
    f"?lon={LON}&lat={LAT}"
    + "".join(f"&property={p}" for p in SOIL_PROPERTIES)
    + "".join(f"&depth={d}" for d in SOIL_DEPTHS)
    + "".join(f"&value={v}" for v in SOIL_VALUES)
)
SOIL_PATH = RAW / f"soilgrids_point_{LAT:.2f}N_{LON:.2f}E.json"
SOIL_FALLBACK = PROCESSED / "soilgrids_site.json"


def fetch(url: str, timeout: int = 180, retries: int = 3, wait: int = 10) -> bytes:
    """GET a URL, retrying transient failures. No auth, no key."""
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "field-shift/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise urllib.error.HTTPError(url, resp.status, resp.reason, resp.headers, None)
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - any network failure is retried
            last = exc
            print(f"  attempt {attempt}/{retries} failed: {exc}", file=sys.stderr)
            if attempt < retries:
                time.sleep(wait * attempt)
    raise RuntimeError(f"could not fetch {url}") from last


def get_power(force: bool) -> Path:
    if POWER_PATH.exists() and not force:
        print(f"POWER: cached at {POWER_PATH.relative_to(ROOT)} ({POWER_PATH.stat().st_size} B)")
        return POWER_PATH
    print(f"POWER: GET {POWER_URL}")
    body = fetch(POWER_URL)
    text = body.decode("utf-8")
    if "-END HEADER-" not in text or "PRECTOTCORR" not in text:
        raise RuntimeError("POWER response is not the expected CSV (no header block)")
    POWER_PATH.parent.mkdir(parents=True, exist_ok=True)
    POWER_PATH.write_bytes(body)
    print(f"POWER: wrote {POWER_PATH.relative_to(ROOT)} ({len(body)} B)")
    return POWER_PATH


def get_soilgrids(force: bool) -> Path:
    if SOIL_PATH.exists() and not force:
        print(f"SoilGrids: cached at {SOIL_PATH.relative_to(ROOT)}")
        return SOIL_PATH
    print(f"SoilGrids: GET {SOIL_URL}")
    try:
        body = fetch(SOIL_URL)
        payload = json.loads(body)
        layers = payload.get("properties", {}).get("layers", [])
        if not layers:
            raise RuntimeError("SoilGrids returned no layers")
        SOIL_PATH.parent.mkdir(parents=True, exist_ok=True)
        SOIL_PATH.write_bytes(body)
        print(f"SoilGrids: wrote {SOIL_PATH.relative_to(ROOT)} ({len(body)} B)")
        return SOIL_PATH
    except Exception as exc:  # noqa: BLE001
        if SOIL_FALLBACK.exists():
            print(
                f"SoilGrids: live query failed ({exc}); using committed fallback "
                f"{SOIL_FALLBACK.relative_to(ROOT)}",
                file=sys.stderr,
            )
            SOIL_PATH.parent.mkdir(parents=True, exist_ok=True)
            SOIL_PATH.write_bytes(SOIL_FALLBACK.read_bytes())
            return SOIL_PATH
        raise


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="refetch even if cached")
    args = ap.parse_args()

    ok = True
    try:
        get_power(args.force)
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"POWER FAILED: {exc}", file=sys.stderr)
    try:
        get_soilgrids(args.force)
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"SoilGrids FAILED: {exc}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
