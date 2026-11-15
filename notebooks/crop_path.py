"""Ordered crop paths, evaluated pair by pair.

The model has one assumption and it is deliberate: each crop affects only the
crop that follows it. A path is therefore read as a chain of single pairs.

    maize then beans then millet  ->  maize->beans, beans->millet

The path is kept as a path. It is never collapsed to a set, because the order
is the thing being compared. Moving one crop moves the pairs, so two paths with
the same crops in a different order give a different result.

The pair directions come from rules/rules.csv, rotation rows only, and each
carries its own label. A row tagged assumed is team expertise for this
prototype; it is a direction with no number, not a measured effect.

This module is imported by the notebook and by scripts/build_app_data.py, so
both paths call one implementation and cannot disagree.

Run standalone to print the pairs:

    python notebooks/crop_path.py maize beans millet
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rules" / "rules.csv"

# The order crops are written in, used only so a path reads left to right.
CROP_LABELS = {
    "maize": "Maize",
    "common_bean": "Common bean",
    "finger_millet": "Finger millet",
    "sorghum": "Sorghum",
    "groundnut": "Groundnut",
    "beans": "Beans",
}


# The rules table writes one pair row with the word "beans", while the rest of
# the pipeline and the page use "common_bean". One alias keeps the pair table
# and the crop list talking about the same crop.
KEY_ALIASES = {"beans": "common_bean"}


def normalise(key: str) -> str:
    """Return the crop key used everywhere else in the pipeline."""
    key = (key or "").strip()
    return KEY_ALIASES.get(key, key)


def _label(key: str) -> str:
    return CROP_LABELS.get(normalise(key), normalise(key).replace("_", " ").title())


def read_pair_rows(path: Path = RULES) -> dict[tuple[str, str], dict]:
    """Return {(first_crop, next_crop): row} for every rotation pair row.

    Two spellings name a pair. A single-crop row such as finger millet records
    the crop it must not follow in its rule text. A row whose crop cell reads
    "beans then maize" names both sides directly. Both become one key, so the
    caller never needs to know which spelling was used.
    """
    pairs: dict[tuple[str, str], dict] = {}
    if not path.exists():
        return pairs
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (row.get("stage") or "").strip() != "rotation":
                continue
            crop = (row.get("crop") or "").strip()
            value = (row.get("value") or "").strip()
            rule = (row.get("rule") or "").strip()
            if " then " in crop:
                first, _, nxt = crop.partition(" then ")
                pairs[(normalise(first), normalise(nxt))] = row
            elif rule.startswith("rotation: not after "):
                first = rule.replace("rotation: not after ", "").strip()
                pairs[(normalise(first), normalise(crop))] = row
            elif crop and value:
                pairs[(normalise(crop), normalise(crop))] = row
    return pairs


def pair_label(row: dict) -> str:
    tag = (row.get("tag") or "").strip().lower()
    if tag == "sourced":
        return "survey"
    return "assumption"


def _direction(row: dict) -> str:
    value = (row.get("value") or "").lower()
    if "not after" in value or "should not" in value:
        return "against"
    return "for"


def _reason(row: dict, first: str, nxt: str) -> str:
    value = (row.get("value") or "").strip()
    if row.get("rule", "").startswith("rotation: not after"):
        return f"{_label(nxt)} should not follow {_label(first)}."
    if value:
        # The table writes "favourable, no number". The page says the direction
        # in a sentence and states separately that no number is held, so the
        # trailing clause is dropped here rather than read aloud twice.
        base = value.split(",")[0].strip()
        return f"{_label(first)} before {_label(nxt)} is {base}."
    return f"{_label(nxt)} after {_label(first)}."


def _note(row: dict) -> str:
    tag = (row.get("tag") or "").strip().lower()
    if tag == "sourced":
        source = (row.get("source") or "").strip()
        page = (row.get("page_or_quote") or "").split("'")[0].strip().rstrip(":")
        body = (row.get("note") or "").strip()
        parts = []
        if source:
            parts.append(f"{source}.")
        if page:
            parts.append(f"{page}.")
        if body:
            parts.append(body[0].upper() + body[1:] + ".")
        parts.append("Not tested: no weed counts are held.")
        return " ".join(parts)
    return (
        "Team expertise, used as a prototype assumption. "
        "Direction only, no number. Not tested."
    )


def evaluate_path(sequence: list[str], path: Path = RULES) -> dict:
    """Assess an ordered crop path pair by pair.

    The path is kept in order. Each adjacent pair is looked up on its own, so
    the result depends on the order given and on which crops are adjacent.
    """
    pairs = read_pair_rows(path)
    steps = []
    for first, nxt in zip(sequence, sequence[1:]):
        row = pairs.get((first, nxt))
        if row is None:
            steps.append(
                {
                    "from": first,
                    "to": nxt,
                    "matched": False,
                    "label": "none",
                    "direction": "unknown",
                    "reason": (
                        f"No rotation rule is held for {_label(nxt)} "
                        f"after {_label(first)}."
                    ),
                    "note": "No row in the released table covers this pair.",
                }
            )
            continue
        steps.append(
            {
                "from": first,
                "to": nxt,
                "matched": True,
                "label": pair_label(row),
                "direction": _direction(row),
                "reason": _reason(row, first, nxt),
                "note": _note(row),
            }
        )
    return {
        "path": list(sequence),
        "path_labels": [_label(c) for c in sequence],
        "assumption": (
            "Each crop affects only the crop that follows it. "
            "An ordered path is assessed pair by pair, first-order only."
        ),
        "steps": steps,
        "n_steps": len(steps),
        "n_matched": sum(1 for s in steps if s["matched"]),
        "n_against": sum(1 for s in steps if s["matched"] and s["direction"] == "against"),
        "n_for": sum(1 for s in steps if s["matched"] and s["direction"] == "for"),
        "n_unmatched": sum(1 for s in steps if not s["matched"]),
    }


def pair_reasons(path: Path = RULES) -> list[dict]:
    """Return every rotation pair as one flat reason row, ordered by crop.

    This is the single place the pair table becomes the rows the app reads, so
    the build and any other caller get the same list in the same order.
    """
    out = []
    for (first, nxt), row in read_pair_rows(path).items():
        if first == nxt:
            continue
        out.append(
            {
                "previous_crop": first,
                "candidate": nxt,
                "label": pair_label(row),
                "direction": _direction(row),
                "reason": _reason(row, first, nxt),
                "note": _note(row),
            }
        )
    out.sort(key=lambda r: (r["previous_crop"], r["candidate"]))
    return out


def compare_paths(paths: list[list[str]], path: Path = RULES) -> dict:
    """Assess several ordered paths, keeping each one separate and in order."""
    results = [evaluate_path(p, path) for p in paths]
    return {
        "assumption": results[0]["assumption"] if results else "",
        "paths": results,
        "n_paths": len(results),
    }


if __name__ == "__main__":
    import json
    import sys

    seq = sys.argv[1:] or ["maize", "beans", "finger_millet"]
    print(json.dumps(evaluate_path(seq), indent=2))
