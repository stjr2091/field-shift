"""Build a static lookup of every ordered crop path a screen can offer.

The screen needs the ordered-path comparison without a server and without
holding its own copy of the pairing logic. This module writes one JSON file,
built ahead of time, that the screen reads like any other data file.

Each entry is produced by calling ``crop_path.evaluate_path``. The pairing logic
lives there and nowhere else. This file is a projection of that model, so the
two cannot disagree about how a path is read.

Key format: crop keys joined by '>', newest last, for example
``maize>common_bean>finger_millet``. Value: the fields a screen renders, under
the same names ``evaluate_path`` returns, so no translation layer is needed.

Coverage: the five crop keys the pipeline uses, at lengths 1 to 3. Length 1 is
included so a single-crop request returns the honest empty result instead of a
missing key.

Blank handling: the screen drops blanks before it builds a key. This index
therefore holds no empty-key entry and no key with an empty segment.

Run from anywhere:

    python scripts/build_path_index.py
"""

from __future__ import annotations

import hashlib
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks"))

import crop_path  # noqa: E402

OUT = ROOT / "results" / "path_index.json"

# The crop keys the pipeline uses, in the order the data file lists them. The
# screen offers a subset of these per history field; the index covers all of
# them so a key the screen can form is always present.
CROP_KEYS = ["maize", "common_bean", "finger_millet", "sorghum", "groundnut"]

# The screen concept has three history fields, so three crops is the longest
# path it can form. One is the shortest, so a single crop still returns a result.
MIN_LENGTH = 1
MAX_LENGTH = 3

# The fields a screen renders, in the order evaluate_path returns them. The
# path itself is not repeated in the value: the key already states it.
RENDER_FIELDS = (
    "steps",
    "n_steps",
    "n_matched",
    "n_for",
    "n_against",
    "n_unmatched",
    "path_labels",
)

STEP_FIELDS = ("from", "to", "matched", "label", "direction", "reason", "note")


def path_key(sequence: list[str]) -> str:
    """The lookup key for one ordered path. Newest last."""
    return ">".join(sequence)


def render_entry(result: dict) -> dict:
    """Keep only the fields a screen renders, under their given names."""
    entry = {name: result[name] for name in RENDER_FIELDS}
    entry["steps"] = [{field: step[field] for field in STEP_FIELDS} for step in result["steps"]]
    return entry


def all_paths() -> list[list[str]]:
    """Every ordered path the screen can form, shortest first."""
    paths = []
    for length in range(MIN_LENGTH, MAX_LENGTH + 1):
        for combo in itertools.product(CROP_KEYS, repeat=length):
            paths.append(list(combo))
    return paths


def build_index() -> dict:
    """The index, keyed by path. Each value comes from the shared model."""
    index = {}
    for sequence in all_paths():
        index[path_key(sequence)] = render_entry(crop_path.evaluate_path(sequence))
    payload = {
        "schema_version": "1.0",
        "key_format": "crop keys joined by '>', newest last",
        "min_length": MIN_LENGTH,
        "max_length": MAX_LENGTH,
        "crop_keys": CROP_KEYS,
        "blank_handling": (
            "Drop blanks before building a key. This index carries no entry "
            "for an empty path and no key with an empty segment."
        ),
        "model": (
            "Each entry is produced by the ordered-path model in notebooks/crop_path.py. "
            "The index is a projection of that model, not a second implementation."
        ),
        "paths": index,
        "n_paths": len(index),
    }
    return payload


def write_index(payload: dict | None = None) -> tuple[Path, dict]:
    """Write the index, and return its path with the payload that was written."""
    payload = payload or build_index()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return OUT, payload


def main() -> None:
    out, payload = write_index()
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size} bytes, sha256 {digest[:16]}…)")
    print(f"paths: {payload['n_paths']} for lengths {MIN_LENGTH} to {MAX_LENGTH}")


if __name__ == "__main__":
    main()
