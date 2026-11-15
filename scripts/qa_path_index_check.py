"""Check that the static path index equals the live ordered-path model.

The index in results/path_index.json is built from notebooks/crop_path.py. This
check proves the projection is faithful, so a screen can trust the file.

Three things are checked.

1. Every key in the index is a real path the model can produce, and the model
   produced the same result for it.
2. A random sample of paths is recomputed live and compared field by field, so
   the file cannot drift from the model without this failing.
3. The index covers the crop universe at lengths 1 to 3, holds no empty-key
   entry and no key with an empty segment, and every entry carries the render
   fields a screen needs.

Run from anywhere:

    python scripts/qa_path_index_check.py

Exit code 0 means every check passed. Any failure exits 1.
"""

from __future__ import annotations

import itertools
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks"))
sys.path.insert(0, str(ROOT / "scripts"))

import crop_path  # noqa: E402
import build_path_index  # noqa: E402

INDEX = ROOT / "results" / "path_index.json"
SAMPLE_SIZE = 25
SEED = 20261115  # fixed, so a rerun checks the same sample

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"PASS  {name}")
        return
    FAILURES.append(name)
    print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))


def main() -> None:
    if not INDEX.exists():
        print("FAIL  path_index.json is missing; run scripts/build_app_data.py first")
        raise SystemExit(1)

    payload = json.loads(INDEX.read_text(encoding="utf-8"))
    index = payload["paths"]
    keys = list(index)

    # --- 1. Every key is a path the model can produce ----------------------
    expected_keys = {build_path_index.path_key(p) for p in build_path_index.all_paths()}
    check(
        "the index holds exactly the paths the model can produce",
        set(keys) == expected_keys,
        f"missing={sorted(expected_keys - set(keys))[:5]} extra={sorted(set(keys) - expected_keys)[:5]}",
    )
    check(
        "the stated path count matches the entries",
        payload["n_paths"] == len(index),
        f"stated {payload['n_paths']}, found {len(index)}",
    )
    check(
        "no key has an empty segment",
        all(all(segment for segment in key.split(">")) for key in keys),
    )
    check("no empty key", "" not in index)
    check(
        "every key segment is a known crop",
        all(
            segment in build_path_index.CROP_KEYS
            for key in keys
            for segment in key.split(">")
        ),
    )

    # --- 2. A random sample equals the live model --------------------------
    rng = random.Random(SEED)
    sample = rng.sample(keys, min(SAMPLE_SIZE, len(keys)))
    mismatches = []
    for key in sample:
        sequence = key.split(">")
        live = build_path_index.render_entry(crop_path.evaluate_path(sequence))
        if live != index[key]:
            mismatches.append(key)
    check(
        f"a random sample of {len(sample)} paths matches the live model exactly",
        not mismatches,
        f"differing keys: {mismatches[:5]}",
    )

    # A whole-length sweep as well, so the sample is not the only evidence.
    sweep_bad = []
    for length in range(build_path_index.MIN_LENGTH, build_path_index.MAX_LENGTH + 1):
        for combo in itertools.product(build_path_index.CROP_KEYS, repeat=length):
            sequence = list(combo)
            key = build_path_index.path_key(sequence)
            live = build_path_index.render_entry(crop_path.evaluate_path(sequence))
            if key not in index or live != index[key]:
                sweep_bad.append(key)
    check(
        "every path at every covered length matches the live model",
        not sweep_bad,
        f"differing keys: {sweep_bad[:5]}",
    )

    # --- 3. Shape the screen needs -----------------------------------------
    entry_bad = [
        key
        for key, value in index.items()
        if set(value) != set(build_path_index.RENDER_FIELDS)
        or any(set(step) != set(build_path_index.STEP_FIELDS) for step in value["steps"])
    ]
    check("every entry carries exactly the render fields", not entry_bad, str(entry_bad[:5]))

    count_bad = []
    for key, value in index.items():
        steps = value["steps"]
        if (
            value["n_steps"] != len(steps)
            or value["n_steps"] != max(len(key.split(">")) - 1, 0)
            or value["n_matched"] != sum(1 for s in steps if s["matched"])
            or value["n_for"] != sum(1 for s in steps if s["matched"] and s["direction"] == "for")
            or value["n_against"] != sum(1 for s in steps if s["matched"] and s["direction"] == "against")
            or value["n_unmatched"] != sum(1 for s in steps if not s["matched"])
        ):
            count_bad.append(key)
    check("every count agrees with its own steps", not count_bad, str(count_bad[:5]))

    check(
        "a single-crop path returns an empty result, not a missing key",
        all(
            index[key]["n_steps"] == 0 and index[key]["steps"] == []
            for key in keys
            if ">" not in key
        ),
    )
    label_bad = [
        key
        for key, value in index.items()
        if value["path_labels"]
        != [crop_path.CROP_LABELS.get(segment, segment.replace("_", " ").title())
            for segment in key.split(">")]
    ]
    check(
        "the labels run in key order, newest last",
        not label_bad,
        str(label_bad[:5]),
    )
    check(
        "the file states how blanks are handled",
        "blank" in payload.get("blank_handling", "").lower(),
    )

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): " + ", ".join(FAILURES))
        raise SystemExit(1)
    print(f"all path index checks passed ({len(index)} paths, sample {len(sample)})")


if __name__ == "__main__":
    main()
