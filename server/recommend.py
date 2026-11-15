"""Pick one crop for a field from the data file and the ordered-path rules.

This module computes and nothing else. It reads results/app_data.json, which the
notebook and the build already produce, and returns the five fields the service
promises. It holds no copy of the rotation rules and no copy of the crop
numbers.

The pairing logic is notebooks/crop_path.py. This module calls it. A rule the
pair model does not hold is reported as unknown, never guessed.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "app_data.json"

sys.path.insert(0, str(ROOT / "notebooks"))
import crop_path  # noqa: E402

# The crops the app may recommend, in the order the data file lists them. This
# is the same order the crop list uses, so a tie breaks the same way twice.
CROP_KEYS = ["maize", "common_bean", "finger_millet", "sorghum", "groundnut"]

# Rank a pairing verdict. A rule that favours the candidate comes first. A pair
# with no rule is not evidence against the crop, so it ranks second. A rule that
# warns against the pair ranks last.
RANK_FOR = 0
RANK_UNKNOWN = 1
RANK_AGAINST = 2


class RequestError(ValueError):
    """The caller sent a request this service cannot answer honestly."""


def load_data(path: Path = DATA) -> dict:
    if not path.exists():
        raise RequestError(
            "results/app_data.json is missing. Run python scripts/build_app_data.py first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _crop_rows(data: dict) -> dict[str, dict]:
    """The crops that passed the sourced-rule cut, keyed by crop key."""
    return {row["crop"]: row for row in data.get("crops", [])}


def _pair_lookup(previous_crops: list[str]) -> dict[tuple[str, str], dict]:
    """Every rotation pair the released table holds, keyed by both crops.

    The rows come from crop_path.pair_reasons(), so this module and the
    notebook read one table through one function.
    """
    out: dict[tuple[str, str], dict] = {}
    for row in crop_path.pair_reasons():
        out[(row["previous_crop"], row["candidate"])] = row
    return out


def normalise_history(previous_crops) -> list[str]:
    """Return the crop history as clean keys, newest last.

    A blank entry is dropped, because it states no crop. An entry the crop list
    does not know is refused: this service will not rank an unknown crop as if
    it were one of the five.
    """
    if previous_crops is None:
        return []
    if not isinstance(previous_crops, list):
        raise RequestError("previous_crops must be a list of crop keys.")
    cleaned = []
    for raw in previous_crops:
        key = crop_path.normalise(str(raw or "").strip().lower())
        if not key:
            continue
        if key not in CROP_KEYS:
            raise RequestError(
                f"previous_crops holds '{key}', which is not one of: {', '.join(CROP_KEYS)}."
            )
        cleaned.append(key)
    return cleaned


def _doy_label(doy: int, year: int = 2021) -> str:
    """Turn a day-of-year into a month and day, using a common year.

    The data file warns that a day-of-year is not a date without a year. The
    label is therefore a month and day only, and the year is never shown.
    """
    day = date(year, 1, 1) + timedelta(days=doy - 1)
    return day.strftime("%-d %B")


def _month_window(row: dict) -> str | None:
    """The planted month range a sourced row states, if the table holds one.

    Some crops are documented by month, not by day. A month range is reported
    as month words, because turning "March to mid-April" into a single day
    would invent a precision the source does not have. A crop with two seasons
    reports both, so the reader is not shown one and left to think it is all.
    """
    windows = []
    for rule_row in row.get("rule_rows", []):
        if rule_row.get("tag") != "sourced":
            continue
        if rule_row.get("parameter") not in ("planting_window", "planting_window_second"):
            continue
        value = (rule_row.get("value") or "").strip()
        if value and value not in windows:
            windows.append(value)
    return ", or ".join(windows) if windows else None


def _window_text(row: dict) -> tuple[str, str]:
    """The planting window, and the basis it rests on."""
    start = row.get("documented_window_start_doy")
    end = row.get("documented_window_end_doy")
    if start and end:
        return (
            f"{_doy_label(start)} to {_doy_label(end)}",
            "A sourced planting window is held for this crop. It gives the "
            "season's planting range, not a date to sow.",
        )
    months = _month_window(row)
    if months:
        return (
            months,
            "Only a month-level planting window is published for this crop, so "
            "no single day is named.",
        )
    return (
        "no sourced planting window is held",
        "This crop has no sourced planting window in the released table, so "
        "none is given. The site's rain onset is reported instead.",
    )


def _onset_text(data: dict) -> str:
    """The site onset sentence, straight from the data file."""
    summary = (data.get("onset") or {}).get("summary") or []
    first = next((r for r in summary if r.get("season") == "first_rains"), None)
    if not first or first.get("onset_doy_median") is None:
        return "The data file holds no rain onset figure for this site."
    median = int(round(first["onset_doy_median"]))
    found = first.get("years_found")
    years = first.get("years_evaluated")
    return (
        f"The first rains start at about {_doy_label(median)} in a median year "
        f"({found} of {years} years). This is a district-scale figure from one "
        "weather cell, not a field reading."
    )


def _ph_check(row: dict, soil_ph):
    """Does the supplied soil pH sit inside the crop's sourced range?

    Returns (rank_penalty, reason_or_none). No soil pH supplied means no check.
    A crop with no sourced pH range is not penalised, because there is nothing
    to test it against.
    """
    if soil_ph is None:
        return 0, None
    bounds = row.get("ph_range")
    if not bounds or bounds[0] is None or bounds[1] is None:
        return 0, f"No sourced soil pH range is held for {row['crop_label']}, so pH was not tested."
    low, high = bounds
    if low <= soil_ph <= high:
        return 0, (
            f"Soil pH {soil_ph} is inside the sourced range for "
            f"{row['crop_label']} ({low} to {high})."
        )
    return 3, (
        f"Soil pH {soil_ph} is outside the sourced range for {row['crop_label']} "
        f"({low} to {high}). This counts against the crop."
    )


def _moisture_note(moisture):
    """Report the supplied moisture word without inventing a threshold.

    The released table has no moisture threshold for any crop, so this value is
    carried in the text and never used to rank a crop.
    """
    if not moisture:
        return None
    text = str(moisture).strip()
    if not text:
        return None
    return (
        f"Moisture was reported as '{text}'. The released table holds no "
        "moisture threshold for any crop, so it did not change the ranking."
    )


def _score(data: dict, history: list[str], soil_ph):
    """Rank the crops the data file offers, with the evidence for each rank."""
    rows = _crop_rows(data)
    pairs = _pair_lookup(history)
    last = history[-1] if history else None
    ranked = []

    for order, key in enumerate(CROP_KEYS):
        row = rows.get(key)
        if row is None:
            continue
        if last and key == last:
            # The last grown crop is never ranked. No rule row advises
            # repeating the crop just grown, so the tool does not offer it,
            # neither as the recommendation nor as the alternative.
            continue
        rank = RANK_UNKNOWN
        pair_row = None
        if last:
            pair_row = pairs.get((last, key))
        if pair_row is not None:
            rank = RANK_AGAINST if pair_row["direction"] == "against" else RANK_FOR

        penalty, ph_reason = _ph_check(row, soil_ph)
        ranked.append(
            {
                "crop": key,
                "row": row,
                "rank": rank + penalty,
                "pair_row": pair_row,
                "ph_reason": ph_reason,
                "ph_penalty": penalty,
                "order": order,
            }
        )

    if not ranked:
        raise RequestError(
            "The data file holds no crop that passed the sourced-rule cut, so no "
            "crop can be recommended."
        )
    ranked.sort(key=lambda item: (item["rank"], item["order"]))
    return ranked


def _pair_reason(item: dict, last) -> str:
    """The rotation sentence for one candidate, labelled by what backs it."""
    pair_row = item["pair_row"]
    if pair_row is None:
        if last is None:
            return "No previous crop was given, so rotation was not judged."
        return (
            f"No rotation rule is held for {item['row']['crop_label']} after "
            f"{crop_path.CROP_LABELS.get(last, last)}; the pair is unknown."
        )
    if pair_row["label"] == "survey":
        return f"{pair_row['reason'].rstrip('.')}; this rests on farmer survey knowledge, not a trial."
    return f"{pair_row['reason'].rstrip('.')}; this is a direction only, with no measured number."


def season_assumption(data: dict) -> str:
    """The one sentence that states which season this advice assumes.

    The request holds no season field, so every window is built on the first
    rains season. The sentence names that pick and the data fact that governs
    it, so the assumption is never silent. It is built from the data file
    only, with no model call.
    """
    head = (
        "No planting season was entered, so this advice assumes the first rains "
        "season, the main season"
    )
    summary = (data.get("onset") or {}).get("summary") or []
    first = next((r for r in summary if r.get("season") == "first_rains"), None)
    if not first or first.get("onset_doy_median") is None:
        return (
            head + "; the data file holds no rain onset figure, so the window rests "
            "on the crop's sourced planting window alone."
        )
    source_name = ""
    for source in (data.get("meta") or {}).get("sources") or []:
        if "POWER" in str(source.get("name") or ""):
            source_name = str(source["name"]).split(" (")[0]
            break
    period = data.get("period") or {}
    span = f"{str(period.get('start_date', ''))[:4]} to {str(period.get('end_date', ''))[:4]}"
    median = int(round(first["onset_doy_median"]))
    found = first.get("years_found")
    years = first.get("years_evaluated")
    return (
        head + "; the window rests on the crop's sourced planting window and the "
        f"site's rain onset analysis of {source_name}, {span} "
        f"(the middle start date was about {_doy_label(median)}, and an onset was "
        f"found in {found} of {years} years)."
    )


def recommend(previous_crops, soil_ph=None, moisture=None, data: dict | None = None) -> dict:
    """Return the five fields the service promises, plus the evidence used.

    Every field is computed here. No sentence in this result is written by a
    language model.
    """
    data = data if data is not None else load_data()
    history = normalise_history(previous_crops)

    if soil_ph is not None:
        try:
            soil_ph = float(soil_ph)
        except (TypeError, ValueError):
            raise RequestError("soil_ph must be a number.")
        if not 0 < soil_ph <= 14:
            raise RequestError("soil_ph must be between 0 and 14.")

    ranked = _score(data, history, soil_ph)
    best = ranked[0]
    # A crop is not its own alternative. The next candidate that is a different
    # crop is offered, so the reader is never told to plant the same crop twice.
    alternative = next((item for item in ranked[1:] if item["crop"] != best["crop"]), None)
    row = best["row"]
    last = history[-1] if history else None

    # Where more than one crop carries the same rank, the order of the crop list
    # decided, not the evidence. Say so rather than let the order look like a
    # finding.
    tied = [item for item in ranked if item["rank"] == best["rank"]]
    tie_note = None
    tie_line = None
    if len(tied) > 1:
        names = ", ".join(item["row"]["crop_label"] for item in tied)
        tie_note = (
            f"{names} rank the same on the rules held. The crop list order chose "
            "between them, not the evidence."
        )
        # The same disclosure in the shortest form a card can carry. The card
        # must state it, because a reader who sees one crop named will otherwise
        # read a tie as a finding.
        tie_line = (
            f"The crops tie. No rule separated them, so the list order decided. "
            f"Tied: {names}."
        )

    window, window_basis = _window_text(row)
    onset = _onset_text(data)
    season_line = season_assumption(data)
    last_label = crop_path.CROP_LABELS.get(last, last) if last else None
    last_crop_guard = (
        f"{last_label} was the last crop; this tool does not advise the same crop "
        "again here."
        if last
        else None
    )
    reasons = [_pair_reason(best, last)]
    if best["ph_reason"]:
        reasons.append(best["ph_reason"])
    reasons.append(f"Planting window: {window}. {window_basis}")
    reasons.append(onset)
    if last_crop_guard:
        reasons.append(last_crop_guard)
    if tie_line:
        # Second, right after the reason, so it is read with the recommendation
        # and not as a footnote at the end.
        reasons.append(tie_line)
    note = _moisture_note(moisture)
    if note:
        reasons.append(note)
    if alternative is not None:
        alt_row = alternative["row"]
        alt_window, _ = _window_text(alt_row)
        reasons.append(
            f"Alternative: {alt_row['crop_label']}, window {alt_window}. "
            + _pair_reason(alternative, last)
        )

    why = reasons[0]
    if best["ph_penalty"]:
        why = (
            f"{reasons[0]} Soil pH {soil_ph} is outside this crop's sourced range, "
            "so this is the least-bad match, not a good one."
        )

    return {
        "recommended_crop": row["crop_label"],
        "when": window,
        "why": why,
        "alternative": alternative["row"]["crop_label"] if alternative else "none held",
        "reasons": reasons,
        "season_assumption": season_line,
        # Evidence a card writer may use. Never shown as advice on its own.
        "facts": {
            "previous_crops": history,
            "site": (data.get("site") or {}).get("name"),
            "site_scale_note": (data.get("site") or {}).get("scale_note"),
            "window": window,
            "window_basis": window_basis,
            "onset": onset,
            "season_assumption": season_line,
            "last_crop_guard": last_crop_guard,
            "soil_ph": soil_ph,
            "moisture": moisture,
            "crop_status": row.get("status"),
            "unknown_rules": row.get("unknown_rules", []),
            "pair_label": (best["pair_row"] or {}).get("label"),
            "pair_direction": (best["pair_row"] or {}).get("direction"),
            # The crop the direction starts from. A guard that reads the pair
            # sentence needs both ends, and the second end is already in the
            # result as the recommended crop.
            "pair_from": history[-1].replace("_", " ") if history else None,
            "assumption": data.get("crop_path_assumption"),
            # The tie disclosure, in the form the card must carry. Absent when
            # no tie occurred, so a card is never told to claim one.
            "tie_line": tie_line,
            "tied_crops": [item["row"]["crop_label"] for item in tied]
            if len(tied) > 1
            else [],
        },
    }
