"""Analysis helpers for the Field Shift notebook: POWER parsing, monthly
climatology, onset detection, soil summary, and the site_climate.json payload.

Every number that reaches results/site_climate.json is produced by a named
function in this file. The notebook is a thin driver over these functions, so a
QA check can go from a value in the JSON to one function here.

Run standalone to rebuild the outputs without a notebook:

    python notebooks/field_shift_data.py

Inputs (see scripts/download_data.py):
    data/raw/power_daily_1.35N_32.45E_1991-2025.csv
    data/raw/soilgrids_point_1.35N_32.45E.json   (falls back to data/processed)

Outputs:
    results/site_climate.json
    results/fig_monthly_rain_climatology.png
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

# --- Site and period --------------------------------------------------------
SITE_NAME = "Nakasongola"
LAT = 1.35
LON = 32.45
START = date(1991, 1, 1)
END = date(2025, 12, 31)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
POWER_CSV = RAW / f"power_daily_{LAT:.2f}N_{LON:.2f}E_1991-2025.csv"
SOIL_RAW = RAW / f"soilgrids_point_{LAT:.2f}N_{LON:.2f}E.json"
SOIL_FALLBACK = PROCESSED / "soilgrids_site.json"

# --- Assumption: the planting criterion ------------------------------------
# Stated once, here and in docs/plan.md. It is OUR assumption, not a sourced
# agronomic rule: planting is possible when a crop's rainfall threshold is met
# over a rolling 10-day sum and root-zone wetness is at or above 0.40.
# Crop thresholds come from rules/rules.csv; until those rows exist we screen
# the site with 20 mm per 10 days and show the sensitivity to 15 and 25 mm.
ONSET_RAIN_10D_MM = 20.0
ONSET_GWETROOT_MIN = 0.40
ONSET_RAIN_10D_SENSITIVITY = (15.0, 20.0, 25.0)

# A "dry day" is < 1 mm, the usual meteorological cutoff at daily resolution.
DRY_DAY_MM = 1.0
DRY_SPELL_REPORT_DAYS = 30

# Rainy-season search windows (month, day). These bound where we look for an
# onset; they are not a claim that every year has two seasons.
SEASONS = {
    "first_rains": ((2, 1), (5, 31)),
    "second_rains": ((8, 1), (11, 30)),
}

POWER_PARAMS = ["PRECTOTCORR", "T2M", "GWETROOT"]
COL = {"PRECTOTCORR": "rain_mm", "T2M": "t2m_c", "GWETROOT": "gwetroot"}
SENTINEL = -999.0


# --- POWER parsing ----------------------------------------------------------
@dataclass
class PowerData:
    daily: pd.DataFrame  # DatetimeIndex, columns rain_mm, t2m_c, gwetroot
    header: dict  # provenance strings scraped from the CSV header block
    quality: dict  # sentinel / duplicate / missing counts


def read_power_csv(path: Path = POWER_CSV) -> PowerData:
    """Parse a NASA POWER daily point CSV.

    POWER writes a prose header block, then 'YEAR,DOY,<params...>'. Dates are
    rebuilt from YEAR + DOY so leap years are handled by the calendar, not by
    arithmetic on 365.
    """
    text = path.read_text(encoding="utf-8")
    if "-END HEADER-" not in text:
        raise ValueError(f"{path} has no POWER header block")
    header_block, table = text.split("-END HEADER-", 1)
    header = _parse_header(header_block)

    df = pd.read_csv(io.StringIO(table.strip()))
    expected = ["YEAR", "DOY", *POWER_PARAMS]
    missing_cols = [c for c in expected if c not in df.columns]
    if missing_cols:
        raise ValueError(f"POWER CSV missing columns: {missing_cols}")

    sentinel_counts, out = {}, {}
    for param in POWER_PARAMS:
        series = pd.to_numeric(df[param], errors="coerce")
        sentinel_counts[param] = int((series == SENTINEL).sum())
        out[COL[param]] = series.replace(SENTINEL, float("nan"))

    dates = pd.to_datetime(df["YEAR"].astype(str), format="%Y") + pd.to_timedelta(
        df["DOY"] - 1, unit="D"
    )
    # Build from arrays, not Series: passing a Series dict with a foreign index
    # silently reindexes every column to NaN.
    daily = pd.DataFrame(
        {name: series.to_numpy() for name, series in out.items()},
        index=pd.DatetimeIndex(dates, name="date"),
    ).sort_index()

    duplicates = int(daily.index.duplicated().sum())
    if duplicates:
        daily = daily[~daily.index.duplicated(keep="first")]

    expected_days = pd.date_range(START, END, freq="D")
    missing = expected_days.difference(daily.index)

    quality = {
        "days_expected": int(len(expected_days)),
        "days_present": int(len(daily)),
        "duplicate_dates": duplicates,
        "missing_dates_count": int(len(missing)),
        "missing_dates_sample": [d.strftime("%Y-%m-%d") for d in missing[:10]],
        "sentinel_counts": sentinel_counts,
        "sentinel_value": SENTINEL,
        "nan_counts": {c: int(daily[c].isna().sum()) for c in daily.columns},
    }
    return PowerData(daily=daily, header=header, quality=quality)


def _parse_header(block: str) -> dict:
    header: dict = {"parameters": {}}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith(("-BEGIN", "-END")):
            continue
        if line.startswith("Location:"):
            header["location"] = line
        elif line.startswith("elevation"):
            header["elevation"] = line
        elif line.startswith("Dates"):
            header["dates"] = line
        elif line.startswith("The value for missing"):
            header["missing_value_note"] = line
        elif line.split()[:1] and line.split()[0] in POWER_PARAMS:
            parts = line.split(None, 1)
            header["parameters"][parts[0]] = parts[1].strip() if len(parts) > 1 else ""
    return header


# --- Monthly climatology ----------------------------------------------------
def monthly_total_series(daily: pd.DataFrame) -> pd.DataFrame:
    """Rainfall total per calendar month, keeping only complete months.

    A month is complete when every one of its days is present and every rain
    value is non-missing. Incomplete months are dropped from the climatology and
    counted, never filled.
    """
    rain = daily["rain_mm"]
    frame = pd.DataFrame({"rain_mm": rain, "t2m_c": daily["t2m_c"], "gwetroot": daily["gwetroot"]})
    frame["year"] = frame.index.year
    frame["month"] = frame.index.month
    frame["days_in_month"] = frame.index.days_in_month

    grouped = frame.groupby(["year", "month"])
    totals = grouped.agg(
        rain_mm=("rain_mm", "sum"),
        days_present=("rain_mm", "size"),
        rain_days_missing=("rain_mm", lambda s: int(s.isna().sum())),
        t2m_c=("t2m_c", "mean"),
        gwetroot=("gwetroot", "mean"),
        days_in_month=("days_in_month", "first"),
    ).reset_index()
    totals["complete"] = (totals["days_present"] == totals["days_in_month"]) & (
        totals["rain_days_missing"] == 0
    )
    return totals


def monthly_climatology(totals: pd.DataFrame) -> tuple[list[dict], dict]:
    """Per-month statistics across years, plus the annual summary."""
    rows = []
    for month in range(1, 13):
        block = totals[(totals["month"] == month) & totals["complete"]]
        rain = block["rain_mm"]
        rows.append(
            {
                "month": month,
                "rain_mm_mean": round(float(rain.mean()), 1),
                "rain_mm_median": round(float(rain.median()), 1),
                "rain_mm_p25": round(float(rain.quantile(0.25)), 1),
                "rain_mm_p75": round(float(rain.quantile(0.75)), 1),
                "rain_mm_min": round(float(rain.min()), 1),
                "rain_mm_max": round(float(rain.max()), 1),
                "n_years": int(len(block)),
                "t2m_mean_c": round(float(block["t2m_c"].mean()), 2),
                "gwetroot_mean": round(float(block["gwetroot"].mean()), 3),
            }
        )

    annual = []
    for year, block in totals.groupby("year"):
        if len(block) == 12 and block["complete"].all():
            annual.append(float(block["rain_mm"].sum()))
    annual_s = pd.Series(annual, dtype=float) if annual else pd.Series(dtype=float)
    summary = {
        "n_years_complete": int(len(annual_s)),
        "rain_mm_mean": round(float(annual_s.mean()), 1) if len(annual_s) else None,
        "rain_mm_median": round(float(annual_s.median()), 1) if len(annual_s) else None,
        "rain_mm_min": round(float(annual_s.min()), 1) if len(annual_s) else None,
        "rain_mm_max": round(float(annual_s.max()), 1) if len(annual_s) else None,
    }
    return rows, summary


# --- Onset ------------------------------------------------------------------
def rolling_sum(series: pd.Series, window: int) -> pd.Series:
    """Trailing rolling sum; NaN when any value in the window is missing."""
    return series.rolling(window, min_periods=window).sum()


def detect_onset(
    daily: pd.DataFrame,
    year: int,
    window: tuple[tuple[int, int], tuple[int, int]],
    rain_10d_mm: float = ONSET_RAIN_10D_MM,
    gwetroot_min: float = ONSET_GWETROOT_MIN,
) -> dict:
    """First day the 10-day rainfall sum crosses the threshold in the window.

    The day qualifies when (a) the trailing 10-day rain sum is at or above
    rain_10d_mm, (b) root-zone wetness that day is at or above gwetroot_min, and
    (c) the rain sum over the previous 10 days was below the threshold.

    Condition (c) is what makes this an *onset* rather than the first day of an
    already-wet period: without it, a window that opens in the middle of the
    rains returns the window's first day every year, which is an artefact of
    where we started looking, not a fact about the weather.
    """
    rain = rolling_sum(daily["rain_mm"], 10)
    rain_prev = rain.shift(10)  # sum over the 10 days before each day
    start = date(year, *window[0])
    end = date(year, *window[1])

    onset: date | None = None
    stats = {"rain_10d_mm": None, "gwetroot": None, "rain_prev_10d_mm": None}
    for day in pd.date_range(start, end, freq="D"):
        if day not in rain.index:
            continue
        now, prev = rain.loc[day], rain_prev.loc[day]
        wet = daily.at[day, "gwetroot"]
        if pd.isna(now) or pd.isna(wet):
            continue
        if now >= rain_10d_mm and wet >= gwetroot_min and (pd.isna(prev) or prev < rain_10d_mm):
            onset = day.date()
            stats = {
                "rain_10d_mm": round(float(now), 1),
                "gwetroot": round(float(wet), 3),
                "rain_prev_10d_mm": None if pd.isna(prev) else round(float(prev), 1),
            }
            break

    row = {
        "year": year,
        "onset_found": onset is not None,
        "onset_date": onset.isoformat() if onset else None,
        "onset_doy": onset.timetuple().tm_yday if onset else None,
        **stats,
    }

    if onset is None:
        row.update(
            {
                "rain_next_30d_mm": None,
                "dry_days_next_30d": None,
                "longest_dry_spell_next_30d": None,
            }
        )
        return row

    window30 = daily.loc[onset : onset + timedelta(days=DRY_SPELL_REPORT_DAYS - 1)]
    dry = window30["rain_mm"] < DRY_DAY_MM
    row.update(
        {
            "rain_next_30d_mm": round(
                float(window30["rain_mm"].sum(skipna=True)), 1
            )
            if window30["rain_mm"].notna().any()
            else None,
            "dry_days_next_30d": int(dry.sum()),
            "longest_dry_spell_next_30d": int(_longest_run(dry.tolist())),
        }
    )
    return row


def _longest_run(flags: list[bool]) -> int:
    best = run = 0
    for flag in flags:
        run = run + 1 if flag else 0
        best = max(best, run)
    return best


def onset_table(
    daily: pd.DataFrame,
    rain_10d_mm: float = ONSET_RAIN_10D_MM,
    gwetroot_min: float = ONSET_GWETROOT_MIN,
) -> list[dict]:
    rows = []
    for season, window in SEASONS.items():
        for year in range(START.year, END.year + 1):
            rows.append(
                {
                    "season": season,
                    "window_start": date(year, *window[0]).isoformat(),
                    "window_end": date(year, *window[1]).isoformat(),
                    **detect_onset(daily, year, window, rain_10d_mm, gwetroot_min),
                }
            )
    return rows


def onset_summary(onsets: list[dict], daily: pd.DataFrame) -> list[dict]:
    summaries = []
    for season, window in SEASONS.items():
        rows = [r for r in onsets if r["season"] == season]
        found = [r for r in rows if r["onset_found"]]
        doys = pd.Series([r["onset_doy"] for r in found], dtype=float)
        sensitivity = []
        for threshold in ONSET_RAIN_10D_SENSITIVITY:
            alt = [
                detect_onset(daily, r["year"], window, threshold)
                for r in rows
            ]
            alt_doys = pd.Series(
                [a["onset_doy"] for a in alt if a["onset_found"]], dtype=float
            )
            sensitivity.append(
                {
                    "rain_10d_threshold_mm": threshold,
                    "years_found": int(len(alt_doys)),
                    "onset_doy_median": round(float(alt_doys.median()), 1)
                    if len(alt_doys)
                    else None,
                }
            )
        summaries.append(
            {
                "season": season,
                "window_start_md": f"{window[0][0]:02d}-{window[0][1]:02d}",
                "window_end_md": f"{window[1][0]:02d}-{window[1][1]:02d}",
                "years_evaluated": len(rows),
                "years_found": len(found),
                "onset_doy_median": round(float(doys.median()), 1) if len(doys) else None,
                "onset_doy_p25": round(float(doys.quantile(0.25)), 1) if len(doys) else None,
                "onset_doy_p75": round(float(doys.quantile(0.75)), 1) if len(doys) else None,
                "onset_doy_min": int(doys.min()) if len(doys) else None,
                "onset_doy_max": int(doys.max()) if len(doys) else None,
                "years_with_dry_spell_ge_7d_in_next_30d": int(
                    sum(
                        1
                        for r in found
                        if r["longest_dry_spell_next_30d"] is not None
                        and r["longest_dry_spell_next_30d"] >= 7
                    )
                ),
                "threshold_sensitivity": sensitivity,
            }
        )
    return summaries


# --- Soil -------------------------------------------------------------------
DEPTH_WEIGHTS = {"0-5cm": 5.0, "5-15cm": 10.0, "15-30cm": 15.0}
SOIL_PROPERTIES = ["phh2o", "clay", "sand", "silt"]


def read_soilgrids(path: Path | None = None) -> dict:
    """Summarise the SoilGrids point extract, depth-weighted over 0-30 cm.

    SoilGrids returns mapped integers with a conversion factor per property:
    texture in g/kg (divide by 10 for %), pH as pH x 10 (divide by 10).
    """
    path = path or (SOIL_RAW if SOIL_RAW.exists() else SOIL_FALLBACK)
    payload = json.loads(path.read_text(encoding="utf-8"))
    layers = {layer["name"]: layer for layer in payload["properties"]["layers"]}

    result: dict = {
        "source_file": str(path.relative_to(ROOT)),
        "properties": {},
    }
    for name in SOIL_PROPERTIES:
        layer = layers.get(name)
        if layer is None:
            result["properties"][name] = None
            continue
        factor = float(layer["unit_measure"]["d_factor"])
        mapped = layer["unit_measure"]["mapped_units"]
        depths = {}
        weighted = 0.0
        weight_total = 0.0
        for depth in layer["depths"]:
            label = depth["label"]
            mean = depth["values"].get("mean")
            median = depth["values"].get("Q0.5")
            if mean is None:
                continue
            value = mean / factor
            depths[label] = {
                "mean": round(value, 2),
                "median": None if median is None else round(median / factor, 2),
            }
            weight = DEPTH_WEIGHTS.get(label, 0.0)
            weighted += value * weight
            weight_total += weight
        result["properties"][name] = {
            "mapped_units": mapped,
            "unit": "pH" if name == "phh2o" else "%",
            "depth_weighted_0_30cm": round(weighted / weight_total, 2) if weight_total else None,
            "depths": depths,
        }

    soil = {k: v["depth_weighted_0_30cm"] for k, v in result["properties"].items() if v}
    result["summary_0_30cm"] = {
        "ph_h2o": soil.get("phh2o"),
        "clay_pct": soil.get("clay"),
        "sand_pct": soil.get("sand"),
        "silt_pct": soil.get("silt"),
    }
    texture_sum = sum(
        v for v in (result["summary_0_30cm"]["clay_pct"], result["summary_0_30cm"]["sand_pct"], result["summary_0_30cm"]["silt_pct"]) if v
    )
    result["texture_sum_pct"] = round(texture_sum, 2)
    return result


# --- Payload ----------------------------------------------------------------
def build_site_climate() -> dict:
    power = read_power_csv()
    daily = power.daily
    totals = monthly_total_series(daily)
    monthly, annual = monthly_climatology(totals)
    onsets = onset_table(daily)
    summaries = onset_summary(onsets, daily)

    raw_bytes = POWER_CSV.read_bytes()
    gwet_below = int((daily["gwetroot"] < ONSET_GWETROOT_MIN).sum())

    incomplete = totals[~totals["complete"]]
    return {
        "meta": {
            "product": "site_climate",
            "site": {
                "name": SITE_NAME,
                "latitude": LAT,
                "longitude": LON,
                "scale_note": (
                    "One NASA POWER grid cell (0.5 x 0.625 deg, ~50 km). "
                    "District-scale, not parcel-scale."
                ),
            },
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "period": {
                "start_date": START.isoformat(),
                "end_date": END.isoformat(),
                "n_days_expected": power.quality["days_expected"],
                "n_days_present": power.quality["days_present"],
            },
            "sources": {
                "power": {
                    "name": "NASA POWER daily point API",
                    "community": "AG",
                    "parameters": POWER_PARAMS,
                    "url": (
                        "https://power.larc.nasa.gov/api/temporal/daily/point"
                        "?parameters=PRECTOTCORR,T2M,GWETROOT&community=AG"
                        f"&longitude={LON}&latitude={LAT}"
                        "&start=19910101&end=20251231&format=CSV"
                    ),
                    "header": power.header,
                },
                "soilgrids": {
                    "name": "ISRIC SoilGrids v2.0 point query",
                    "url": (
                        "https://rest.isric.org/soilgrids/v2.0/properties/query"
                        f"?lon={LON}&lat={LAT}&property=phh2o&property=clay"
                        "&property=sand&property=silt&depth=0-5cm&depth=5-15cm"
                        "&depth=15-30cm&value=mean&value=Q0.5"
                    ),
                },
            },
            "raw_cache": {
                "file": str(POWER_CSV.relative_to(ROOT)),
                "bytes": len(raw_bytes),
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            },
            "assumptions": [
                "Planting is possible when a crop's rainfall threshold is met over a rolling "
                "10-day sum and root-zone wetness (GWETROOT) is at or above 0.40. This is an "
                "assumption, not a sourced agronomic rule.",
                "Until crop rules land in rules/rules.csv, the site-wide screening threshold is "
                f"{ONSET_RAIN_10D_MM:.0f} mm per 10 days; onset detection is shown at 15, 20 and "
                "25 mm in onset_summary[].threshold_sensitivity.",
                "An onset is the first day the 10-day sum crosses the threshold (previous "
                "10-day sum below it), inside the season search window. Crossing matters: "
                "without it a window opening mid-season returns the window's first day.",
                f"A dry day is rainfall below {DRY_DAY_MM:.0f} mm; dry-spell risk is reported "
                f"for the {DRY_SPELL_REPORT_DAYS} days after onset only.",
                "Season search windows bound where onset is looked for; they do not assert "
                "that every year has two distinct rainy seasons.",
            ],
            "method_notes": [
                "Monthly rainfall climatology uses whole calendar months only: a month enters "
                "the statistics when every day is present and no rain value is missing.",
                "POWER -999 is treated as missing (NaN), never as a value; counts are reported "
                "in data_quality.sentinel_counts.",
                "Annual totals use years with 12 complete months.",
            ],
        },
        "monthly_climatology": monthly,
        "annual": annual,
        "onset_definition": {
            "rain_10d_threshold_mm": ONSET_RAIN_10D_MM,
            "gwetroot_min": ONSET_GWETROOT_MIN,
            "rain_variable": "PRECTOTCORR (mm/day)",
            "soil_variable": "GWETROOT (root-zone soil wetness, 0-1)",
            "crossing_rule": "trailing 10-day rain sum >= threshold and previous 10-day sum < threshold",
            "dry_day_mm": DRY_DAY_MM,
            "dry_spell_window_days": DRY_SPELL_REPORT_DAYS,
        },
        "onset_by_year": onsets,
        "onset_summary": summaries,
        "soil": read_soilgrids(),
        "data_quality": {
            **power.quality,
            "months_incomplete": int(len(incomplete)),
            "months_incomplete_sample": [
                f"{int(r.year)}-{int(r.month):02d}" for r in incomplete.itertuples()
            ][:10],
            "gwetroot_days_below_gate": gwet_below,
            "gwetroot_gate_note": (
                "GWETROOT never fell below the 0.40 gate in this record, so the soil condition "
                "never binds and onset is decided by rainfall alone. Reported, not dropped."
                if gwet_below == 0
                else "GWETROOT fell below the 0.40 gate on some days; those days cannot be an onset."
            ),
        },
    }


def write_outputs(payload: dict | None = None) -> Path:
    payload = payload or build_site_climate()
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "site_climate.json"
    out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return out


def plot_monthly_climatology(monthly: list[dict], path: Path | None = None) -> Path:
    """Rainfall climatology as mean with the 25th-75th percentile band."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = path or RESULTS / "fig_monthly_rain_climatology.png"
    path.parent.mkdir(parents=True, exist_ok=True)

    months = [r["month"] for r in monthly]
    mean = [r["rain_mm_mean"] for r in monthly]
    low = [r["rain_mm_p25"] for r in monthly]
    high = [r["rain_mm_p75"] for r in monthly]

    fig, ax = plt.subplots(figsize=(7.5, 4.0), dpi=150)
    ax.fill_between(months, low, high, color="#7fb3d5", alpha=0.35, label="25th-75th percentile of years")
    ax.plot(months, mean, color="#1f4e79", linewidth=2, marker="o", markersize=4, label="1991-2025 mean")
    ax.set_xticks(months)
    ax.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_xlabel("Month")
    ax.set_ylabel("Rainfall (mm per month)")
    ax.set_title(f"{SITE_NAME} monthly rainfall climatology, 1991-2025\nNASA POWER daily, district-scale grid cell")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


if __name__ == "__main__":
    payload = build_site_climate()
    out = write_outputs(payload)
    fig = plot_monthly_climatology(payload["monthly_climatology"])
    print(f"wrote {out.relative_to(ROOT)}")
    print(f"wrote {fig.relative_to(ROOT)}")
    print(f"onset first_rains median DOY: {payload['onset_summary'][0]['onset_doy_median']}")
    print(f"annual mean rain: {payload['annual']['rain_mm_mean']} mm")
