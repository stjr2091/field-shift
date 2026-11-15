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

# Why a crop with rows is still cut. Keyed by crop, so the app can state the
# reason rather than only the count. Kept beside the cut rule it explains.
CUT_REASONS = {
    "finger_millet": "The water row is reference evidence from the millet chapter, "
    "500-1,000 mm, and is not a Soroti threshold. The planting window is borrowed from "
    "the maize row. Neither counts toward the three of four.",
}

# Rotation reasons that a previous-crop choice can match. Each one carries its
# own label, so an assumption is never shown as a measured effect. The order of
# the crops in a sequence is kept by the app; this list only says what a pair
# means. Text and citation come from the released rules table.
SEQUENCE_REASONS = [
    {
        "previous_crop": "sorghum",
        "candidate": "finger_millet",
        "label": "survey",
        "direction": "against",
        "reason": "Millet should not follow sorghum.",
        "note": "Farmer knowledge from a Teso survey, not a trial. "
        "R8030 Final Technical Report, page 50.",
    },
    {
        "previous_crop": "common_bean",
        "candidate": "maize",
        "label": "assumption",
        "direction": "for",
        "reason": "Beans before maize is generally favourable.",
        "note": "Direction only. No number.",
    },
    {
        "previous_crop": "maize",
        "candidate": "common_bean",
        "label": "assumption",
        "direction": "for",
        "reason": "Maize before beans is neutral to favourable.",
        "note": "Direction only.",
    },
]

# Day-weighted month lengths, used only to turn twelve monthly means into one
# yearly mean. The data holds no single yearly temperature field, and a plain
# average of months would over-weight February.
MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# The five limitation lines from the released crop rules workbook. They travel
# with the crop rows, so a reader sees them beside the numbers they qualify.
CROP_LIMITATIONS = [
    "Finger millet planting dates for Soroti are borrowed from the MAAIF maize window. "
    "No Soroti millet calendar was found",
    "Finger millet maturity uses FAO EcoCrop's global range, not a Ugandan figure",
    "Rain needed per season uses EcoCrop's yearly ranges, because Soroti's rain behaves "
    "like one long season",
    "Rotation effects (beans before maize and the reverse) give a direction only, with no number",
    "Beans planting dates are national and Eastern region, not Soroti, and two pages of "
    "the manual do not match",
]


def round_or_none(value, digits):
    return None if value is None else round(float(value), digits)


def read_rules():
    """Return {crop: [row, ...]} for every rule row of that crop.

    A row is kept when it carries a tag and a crop. The tag decides whether the
    row counts as sourced: a row tagged assumed or unknown stays in the file so
    the app can show it, but it never counts toward the three-of-four cut.
    """
    if not RULES.exists():
        return {}
    by_crop: dict[str, list[dict]] = {}
    with RULES.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            crop = (row.get("crop") or "").strip()
            tag = (row.get("tag") or "").strip().lower()
            if not crop or not tag:
                continue
            by_crop.setdefault(crop, []).append(
                {key: (value or "").strip() for key, value in row.items() if key}
            )
    return by_crop


def sourced_parameters(rows):
    """The four cut parameters that have at least one row tagged sourced."""
    return {
        row.get("parameter")
        for row in rows
        if row.get("tag") == "sourced" and row.get("parameter") in RULE_PARAMETERS
    }


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
        found = sourced_parameters(rows)
        if len(found) < MIN_SOURCED_RULES:
            continue
        unknown = [name for name in RULE_PARAMETERS if name not in found]

        def first(parameter, field):
            """Read a field from a sourced row, so an assumed row never wins."""
            for row in rows:
                if row.get("parameter") == parameter and row.get("tag") == "sourced":
                    return rule_value(row, field)
            return None

        def pair(parameter):
            """Return [low, high] from a sourced row, or None."""
            low = first(parameter, "value_min")
            high = first(parameter, "value_max")
            if low is None and high is None:
                return None
            return [low, high]

        season_length = first("season_length", "value_min")
        # A planting window reaches the app only from a sourced row. The
        # workbook states one window per crop, so value_min and value_max hold
        # the start and end as day-of-year. A month-level row stays null,
        # because a month cannot be turned into one honest day.
        start = end = None
        for row in rows:
            if row.get("tag") != "sourced":
                continue
            if row.get("parameter") in ("planting_window", "planting_window_start"):
                start = rule_value(row, "value_min")
                if row.get("parameter") == "planting_window":
                    end = rule_value(row, "value_max")
            elif row.get("parameter") == "planting_window_end":
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
                # The 10-day field holds only a 10-day rule. The workbook gives
                # seasonal millimetres, which are not a 10-day trigger, so this
                # stays null and the season figure is kept in its own row.
                "rain_threshold_mm_10d": None,
                "season_length_days": int(season_length) if season_length else None,
                "ph_range": pair("ph_range"),
                "temp_range_c": pair("temp_range"),
                "rules_used": sorted(
                    f"{row.get('crop')}/{row.get('stage')}/{row.get('parameter')}"
                    for row in rows
                ),
                "unknown_rules": unknown,
                # One plain line per unknown rule, so the app can print the gap
                # instead of leaving a cell blank. The threshold sentence is the
                # same for every crop, because no crop has a 10-day figure.
                "unknown_notes": {
                    name: "no planting rainfall threshold is published for this crop, "
                    "so this value stays unknown rather than guessed. "
                    "The season water need is a seasonal total, not a sowing trigger."
                    if name == "planting_rainfall_threshold"
                    else "no sourced value in the released table"
                    for name in unknown
                },
                "source_label": (
                    "threshold unknown: no planting rainfall figure is published. "
                    "Season water need is a seasonal total, not a sowing trigger"
                    if "planting_rainfall_threshold" in unknown and len(unknown) == 1
                    else None
                ),
                "rule_rows": rows,
            }
        )
    return crops


def build_rotation(rules_by_crop):
    """Return the rotation rows that a source backs, as their own list.

    Rotation rows cannot ride in the crops list. A crop pair such as
    "beans then maize" is not a crop, so the build loop over CROP_ORDER never
    reaches it. Each entry states its own tag and what backs it, so the page can
    label a direction rather than present it as a result.

    Only rows tagged sourced are returned. An unsourced direction has nothing
    behind it, and this page does not publish advice it cannot support.
    """
    out = []
    for crop, rows in rules_by_crop.items():
        for row in rows:
            if row.get("stage") != "rotation" or row.get("tag") != "sourced":
                continue
            out.append(
                {
                    "subject": crop,
                    "direction": row.get("value"),
                    "rule": row.get("rule"),
                    "source": row.get("source"),
                    "source_url": row.get("source_url") or None,
                    "page_or_quote": row.get("page_or_quote"),
                    "note": row.get("note"),
                    "tested": False,
                    "test_note": "Not tested. No nitrogen, yield or trial data "
                    "is held, so a rotation effect cannot be measured here.",
                }
            )
    return out


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
    monthly = climate["monthly_climatology"]
    t2m_mean = round(
        sum(row["t2m_mean_c"] * days for row, days in zip(monthly, MONTH_DAYS))
        / sum(MONTH_DAYS),
        2,
    )
    coverage = [
        {
            "crop": crop,
            "crop_label": label,
            "n_rules_sourced": len(sourced_parameters(rules_by_crop.get(crop, []))),
            "n_rules_expected": len(RULE_PARAMETERS),
            "appears": len(sourced_parameters(rules_by_crop.get(crop, [])))
            >= MIN_SOURCED_RULES,
            "cut_reason": CUT_REASONS.get(crop, "")
            if len(sourced_parameters(rules_by_crop.get(crop, []))) < MIN_SOURCED_RULES
            else "",
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
            # One yearly mean, built from the twelve monthly means by month
            # length. The app needs a site temperature to compare with a crop
            # optimum, and it must read that number rather than type it in.
            "t2m_mean_c": t2m_mean,
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
        "crop_rotation": build_rotation(rules_by_crop),
        "sequence_reasons": SEQUENCE_REASONS,
        "crop_limitations": CROP_LIMITATIONS,
        "data_quality": climate["data_quality"],
        "notes": [
            "One NASA POWER cell covers about 50 km. District-scale, not parcel-scale.",
            "Missing days are shown, never filled. This record has none.",
            "Zero rain is a real dry day and stays in every sum.",
            "The rainfall rule for each crop is a seasonal total in millimetres. "
            "No crop in this table has a 10-day rainfall trigger, so the 10-day "
            "threshold field is null for every crop and nothing is guessed into it.",
        ]
        # The five limitation lines also ride in notes, which the schema says the
        # app may show verbatim, so a reader meets them beside the crop numbers.
        + [f"Crop rule limit: {line}" for line in CROP_LIMITATIONS],
    }

    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes, sha256 {digest[:16]}…)")
    print(f"crops: {len(crops)} — data_status.crop_windows = {payload['data_status']['crop_windows']}")


if __name__ == "__main__":
    main()
