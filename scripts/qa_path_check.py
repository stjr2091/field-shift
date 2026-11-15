"""Check the ordered-path model and that the notebook and build agree.

Run from anywhere:

    python scripts/qa_path_check.py

Two things are checked, in the order the review asked for.

1. The ordered comparison. A path is read pair by pair and order changes the
   result. The check asserts this rather than assuming it.

2. Notebook and build agreement on the same inputs, and again on changed
   inputs. The notebook path builds site_climate.json from the raw record. The
   build path turns that into app_data.json. Both call the same pair model, so
   the pair rows must match exactly. Changing an input must change the pair
   rows that depend on it and leave the rest alone.

Exit code 0 means every check passed. Any failure exits 1 and prints the first
mismatch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks"))

import crop_path  # noqa: E402

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"PASS  {name}")
        return
    FAILURES.append(name)
    print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))


def signature(result: dict) -> list[tuple]:
    """The part of a path result that order must be able to change."""
    return [
        (s["from"], s["to"], s["label"], s["direction"], s["matched"])
        for s in result["steps"]
    ]


# --- 1. The ordered comparison ---------------------------------------------
forward = crop_path.evaluate_path(["maize", "common_bean"])
reverse = crop_path.evaluate_path(["common_bean", "maize"])

check(
    "order changes the outcome for a two-crop path",
    signature(forward) != signature(reverse),
    "both orders gave the same pairs",
)
check(
    "forward path reads maize then common bean",
    [s["to"] for s in forward["steps"]] == ["common_bean"],
)
check(
    "reverse path reads common bean then maize",
    [s["to"] for s in reverse["steps"]] == ["maize"],
)

long_path = crop_path.evaluate_path(["maize", "common_bean", "finger_millet"])
check("a three-crop path keeps three crops in order", long_path["path"] == [
    "maize", "common_bean", "finger_millet"])
check("a three-crop path yields two pairs", long_path["n_steps"] == 2)
check(
    "the path is not collapsed to a set",
    [ (s["from"], s["to"]) for s in long_path["steps"] ]
    == [("maize", "common_bean"), ("common_bean", "finger_millet")],
)
check(
    "the middle crop is both a destination and a source",
    long_path["steps"][0]["to"] == long_path["steps"][1]["from"],
)

reordered = crop_path.evaluate_path(["finger_millet", "common_bean", "maize"])
check(
    "reordering the same three crops changes the result",
    signature(long_path) != signature(reordered),
    "the same crops in a different order gave identical pairs",
)

sorghum_path = crop_path.evaluate_path(["sorghum", "finger_millet"])
check(
    "sorghum then millet carries the survey reason against it",
    sorghum_path["n_against"] == 1
    and sorghum_path["steps"][0]["label"] == "survey",
)

deep = crop_path.evaluate_path(["maize", "sorghum", "finger_millet"])
check(
    "a pair two steps back is still read as its own pair",
    deep["steps"][1]["to"] == "finger_millet" and deep["steps"][1]["label"] == "survey",
)
check(
    "one-step model does not test maize against millet",
    all(
        not (s["from"] == "maize" and s["to"] == "finger_millet")
        for s in deep["steps"]
    ),
)

unmatched = crop_path.evaluate_path(["groundnut", "maize"])
check(
    "a pair with no rule stays unmatched rather than guessed",
    unmatched["n_unmatched"] == 1 and unmatched["steps"][0]["label"] == "none",
)

check(
    "no pair reason carries a number",
    all(
        not any(ch.isdigit() for ch in s["reason"])
        for s in long_path["steps"] + deep["steps"] + sorghum_path["steps"]
    ),
)

# --- 2. Notebook and build agreement ---------------------------------------
APP = ROOT / "results" / "app_data.json"
if not APP.exists():
    print("FAIL  app_data.json is missing; run scripts/build_app_data.py first")
    raise SystemExit(1)

data = json.loads(APP.read_text(encoding="utf-8"))
app_pairs = {
    (r["previous_crop"], r["candidate"]): r for r in data["sequence_reasons"]
}
model_pairs = {
    (r["previous_crop"], r["candidate"]): r for r in crop_path.pair_reasons()
}

check(
    "the same inputs give the same pair keys in both paths",
    set(app_pairs) == set(model_pairs),
    f"app={sorted(app_pairs)} model={sorted(model_pairs)}",
)
same_text = all(
    app_pairs[k]["reason"] == model_pairs[k]["reason"]
    and app_pairs[k]["label"] == model_pairs[k]["label"]
    and app_pairs[k]["direction"] == model_pairs[k]["direction"]
    for k in app_pairs
    if k in model_pairs
)
check("the same inputs give the same pair text, label and direction", same_text)

check(
    "every pair row carries a label",
    all(r["label"] in ("survey", "assumption") for r in data["sequence_reasons"]),
)
check(
    "no pair row claims a measured effect",
    all("not tested" in r["note"].lower() for r in data["sequence_reasons"]),
)
check(
    "the one-step assumption is stated in the data the page reads",
    bool(data.get("crop_path_assumption", "").strip()),
)

# Changed inputs: a copy of the table where one pair direction is removed.
import csv  # noqa: E402
import io  # noqa: E402
import tempfile  # noqa: E402

rows = list(csv.reader(io.StringIO(
    (ROOT / "rules" / "rules.csv").read_text(encoding="utf-8"), newline="")))
header, body = rows[0], rows[1:]
col = {name: i for i, name in enumerate(header)}
kept = [r for r in body if r[col["crop"]] != "maize then beans"]
buf = io.StringIO()
writer = csv.writer(buf, lineterminator="\n")
writer.writerow(header)
for r in kept:
    writer.writerow(r)

with tempfile.TemporaryDirectory() as tmp:
    alt = Path(tmp) / "rules_alt.csv"
    alt.write_text(buf.getvalue(), encoding="utf-8")

    changed = crop_path.pair_reasons(alt)
    changed_keys = {(r["previous_crop"], r["candidate"]) for r in changed}
    unchanged_keys = set(model_pairs) - {("maize", "common_bean")}

    check(
        "changing an input changes the pairs that depend on it",
        ("maize", "common_bean") not in changed_keys,
    )
    check(
        "changing an input leaves the other pairs alone",
        unchanged_keys <= changed_keys,
        f"lost {sorted(unchanged_keys - changed_keys)}",
    )

    alt_path = crop_path.evaluate_path(["maize", "common_bean"], alt)
    check(
        "the removed pair becomes unmatched rather than silently dropped",
        alt_path["n_unmatched"] == 1 and alt_path["n_steps"] == 1,
    )

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} check(s): " + ", ".join(FAILURES))
    raise SystemExit(1)
print("all path checks passed")
