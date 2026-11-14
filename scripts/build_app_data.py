"""Build results/app_data.json from results/site_climate.json and rules/rules.csv.

The app reads one file and computes nothing, so this script is the only place
where the two sources are joined. Run from anywhere:

    python scripts/build_app_data.py

It writes results/app_data.json in the shape of docs/app_data_schema.md.

Crop rows are joined from rules/rules.csv. A crop appears only when it has at
least three sourced rules; a crop with fewer is cut, per docs/plan.md. While
rules.csv holds no rows, crops is empty and data_status.crop_windows is
"pending", so the app shows the climate panels and a waiting state. No crop
number is invented here.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIMATE = ROOT / "results" / "site_climate.json"
RULES = ROOT / "rules" / "rules.csv"
OUT = ROOT / "results" / "app_data.json"

SCHEMA_VERSION = "1.0"

# The four rule parameters every crop needs, in the order the app shows them.
RULE_PARAMETERS = [
    "planting_rainfall_threshold",
    "season_length",
    "ph_range",
    "temp_range",
]

# Crops the app knows how to label, in the order docs/app_data_schema.md fixes.
CROP_ORDER = ["maize", "common_bean", "finger_millet", "sorghum", "groundnut"]
CROP_LABELS = {
    "maize": "Maize",
    "common_bean": "Common bean",
    "finger_millet": "Finger millet",
    "sorghum": "Sorghum",
    "groundnut": "Groundnut",
}

MIN_SOURCED_RULES = 3


def round_or_none(value, digits):
    return None if value is None else round(float(value), digits)


def read_rules():
    """Return {crop: [row, ...]} with only rows that carry a real source."""
    if not RULES.exists():
        return {}
    by_crop: dict[str, list[dict]] = {}
    with RULES.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            crop = (row.get("crop") or "").strip()
            source = (row.get("source") or "").strip()
            if not crop or not source or source.lower() == "unknown":
                continue
            by_crop.setdefault(crop, []).append(
                {key: (value or "").strip() for key, value in row.items() if key}
            )
    return by_crop


def rule_value(row, key):
    """Read a numeric cell, treating a blank or non-numeric cell as unknown."""
    raw = row.get(key)
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def build_crops(rules_by_crop):
    crops = []
    for key in CROP_ORDER:
        rows = rules_by_crop.get(key, [])
        if len(rows) < MIN_SOURCED_RULES:
            continue
        found = {row.get("parameter") for row in rows}
        unknown = [name for name in RULE_PARAMETERS if name not in found]

        def first(parameter, field):
            for row in rows:
                if row.get("parameter") == parameter:
                    return rule_value(row, field)
            return None

        season_length = first("season_length", "value_min")
        onsets = [
            row
            for row in rows
            if row.get("parameter") in ("planting_window_start", "planting_window_end")
        ]
        start = end = None
        for row in onsets:
            if row.get("parameter") == "planting_window_start":
                start = rule_value(row, "value_min")
            else:
                end = rule_value(row, "value_min")

        crops.append(
            {
                "crop": key,
                "crop_label": CROP_LABELS.get(key, key.replace("_", " ").title()),
                "status": "sourced" if not unknown else "partial",
                "documented_window_start_doy": int(start) if start else None,
                "documented_window_end_doy": int(end) if end else None,
                "supported_window_start_doy": None,
                "supported_window_end_doy": None,
                "gap_days": None,
                "rain_threshold_mm_10d": first("planting_rainfall_threshold", "value_min"),
                "season_length_days": int(season_length) if season_length else None,
                "ph_range": None,
                "temp_range_c": None,
                "rules_used": sorted(
                    f"{row.get('crop')}/{row.get('stage')}/{row.get('parameter')}"
                    for row in rows
                ),
                "unknown_rules": unknown,
                "rule_rows": rows,
            }
        )
    return crops


def main() -> None:
    climate = json.loads(CLIMATE.read_text(encoding="utf-8"))
    meta = climate["meta"]
    site = meta["site"]
    period = meta["period"]

    crops = build_crops(read_rules())

    # Table 1: rules coverage, so the app can say "sourced out of four".
    # Counted from rules.csv directly, so a crop with no rows reads 0 of 4
    # rather than being flattered by its absence from the crops list.
    rules_by_crop = read_rules()
    coverage = [
        {
            "crop": crop,
            "crop_label": label,
            "n_rules_sourced": len(
                {
                    row.get("parameter")
                    for row in rules_by_crop.get(crop, [])
                    if row.get("parameter") in RULE_PARAMETERS
                }
            ),
            "n_rules_expected": len(RULE_PARAMETERS),
        }
        for crop, label in CROP_LABELS.items()
    ]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_status": {
            "site_climate": "ready",
            "crop_windows": "ready" if crops else "pending",
        },
        "meta": {
            "sources": [
                {
                    "name": "NASA POWER daily point (MERRA-2)",
                    "url": meta["sources"]["power"]["url"],
                    "accessed": "2026-11-14",
                },
                {
                    "name": "ISRIC SoilGrids v2.0 point query",
                    "url": meta["sources"]["soilgrids"]["url"],
                    "accessed": "2026-11-14",
                },
            ],
            "assumptions": [
                "Planting is possible on the first day the trailing 10-day rainfall "
                "sum reaches the threshold, having been below it before, with root-zone "
                "soil wetness at or above 0.40. This is an assumption, not a sourced rule.",
                "This figure is the day the 10-day threshold is first met, not the first "
                "rain day. It can lag the first rain by up to 9 days.",
            ],
            "raw_cache_sha256": meta.get("raw_cache", {}).get("sha256", ""),
            "pipeline": "notebooks/field_shift.ipynb",
        },
        "site": {
            "name": site["name"],
            "lat": site["latitude"],
            "lon": site["longitude"],
            "scale_note": site["scale_note"],
        },
        "period": {
            "start_date": period["start_date"],
            "end_date": period["end_date"],
            "n_years": 35,
        },
        "monthly_climatology": [
            {
                "month": row["month"],
                "rain_mm_mean": round_or_none(row["rain_mm_mean"], 1),
                "rain_mm_median": round_or_none(row["rain_mm_median"], 1),
                "rain_mm_p25": round_or_none(row["rain_mm_p25"], 1),
                "rain_mm_p75": round_or_none(row["rain_mm_p75"], 1),
                "n_years": row["n_years"],
                "t2m_mean_c": round_or_none(row["t2m_mean_c"], 2),
                "gwetroot_mean": round_or_none(row["gwetroot_mean"], 2),
            }
            for row in climate["monthly_climatology"]
        ],
        "annual": {
            "rain_mm_mean": round_or_none(climate["annual"]["rain_mm_mean"], 1),
            "rain_mm_median": round_or_none(climate["annual"]["rain_mm_median"], 1),
            "n_years_complete": climate["annual"]["n_years_complete"],
        },
        "onset": {
            "definition": climate["onset_definition"],
            "summary": [
                {
                    "season": row["season"],
                    "label": "First rains (Feb–May)"
                    if row["season"] == "first_rains"
                    else "Second rains (Aug–Nov)",
                    "window_start_md": row.get("window_start_md"),
                    "window_end_md": row.get("window_end_md"),
                    "onset_doy_median": round_or_none(row["onset_doy_median"], 1),
                    "onset_doy_p25": round_or_none(row["onset_doy_p25"], 1),
                    "onset_doy_p75": round_or_none(row["onset_doy_p75"], 1),
                    "years_evaluated": row["years_evaluated"],
                    "years_found": row["years_found"],
                    "years_with_dry_spell_ge_7d_in_next_30d": row[
                        "years_with_dry_spell_ge_7d_in_next_30d"
                    ],
                    "threshold_sensitivity": row.get("threshold_sensitivity", []),
                }
                for row in climate["onset_summary"]
            ],
            "by_year": [
                {
                    "year": row["year"],
                    "season": row["season"],
                    "onset_date": row["onset_date"],
                    "onset_doy": row["onset_doy"],
                    "onset_found": row["onset_found"],
                    "rain_next_30d_mm": round_or_none(row["rain_next_30d_mm"], 1),
                    "longest_dry_spell_next_30d": row["longest_dry_spell_next_30d"],
                }
                for row in climate["onset_by_year"]
            ],
        },
        "soil": climate["soil"]["summary_0_30cm"]
        | {"texture_sum_pct": climate["soil"]["texture_sum_pct"]},
        "crops": crops,
        "crop_rule_coverage": coverage,
        "data_quality": climate["data_quality"],
        "notes": [
            "One NASA POWER cell covers about 50 km. District-scale, not parcel-scale.",
            "Missing days are shown, never filled. This record has none.",
            "Zero rain is a real dry day and stays in every sum.",
        ],
    }

    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes, sha256 {digest[:16]}…)")
    print(f"crops: {len(crops)} — data_status.crop_windows = {payload['data_status']['crop_windows']}")


if __name__ == "__main__":
    main()
