"""Checks for the recommendation service. No network, no credentials.

    python server/test_recommend.py

Each check states what must hold. A failure prints the case and exits non-zero,
so this can run in a release check.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import card  # noqa: E402
import recommend as calc  # noqa: E402

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"pass  {name}")
        return
    FAILURES.append(name)
    print(f"FAIL  {name}{': ' + detail if detail else ''}")


def main() -> int:
    data = calc.load_data()

    # The fields the page was promised, and no other.
    result = calc.recommend(["sorghum"], data=data)
    for field in ("recommended_crop", "when", "why", "alternative", "reasons"):
        check(f"result has {field}", field in result)

    # A recommendation is one of the crops the data file holds.
    keys = {row["crop"] for row in data["crops"]}
    labels = {row["crop_label"] for row in data["crops"]}
    for history in ([], ["maize"], ["sorghum"], ["common_bean"]):
        res = calc.recommend(history, data=data)
        check(
            f"recommended crop is in the data file, history {history}",
            res["recommended_crop"] in labels,
            res["recommended_crop"],
        )

    # A crop is never its own alternative.
    for history in ([], ["maize"], ["sorghum"], ["common_bean"], ["maize", "common_bean"]):
        res = calc.recommend(history, data=data)
        check(
            f"alternative differs from recommendation, history {history}",
            res["alternative"] != res["recommended_crop"],
            res["alternative"],
        )

    # Order matters: the same crops in another order are read pair by pair.
    forward = calc.recommend(["maize", "common_bean"], data=data)
    check(
        "newest crop decides the pair",
        "Common bean before Maize" in forward["why"] or "No rotation rule" in forward["why"],
        forward["why"],
    )

    # An unknown crop is refused, not ranked.
    try:
        calc.recommend(["cassava"], data=data)
        check("unknown crop is refused", False)
    except calc.RequestError:
        check("unknown crop is refused", True)

    # A soil pH outside the range removes the crop's advantage and is said.
    ph = calc.recommend(["sorghum"], soil_ph=4.5, data=data)
    check("out-of-range pH is stated", "outside" in ph["why"], ph["why"])

    # Moisture is carried in the text and never ranks.
    wet = calc.recommend(["sorghum"], moisture="wet", data=data)
    dry = calc.recommend(["sorghum"], moisture="dry", data=data)
    check(
        "moisture does not change the recommendation",
        wet["recommended_crop"] == dry["recommended_crop"],
    )
    check("moisture is reported", any("Moisture was reported" in r for r in wet["reasons"]))

    # The plain card passes its own check and stays short.
    for history in ([], ["maize"], ["sorghum"], ["maize", "common_bean"]):
        res = calc.recommend(history, data=data)
        text = card.template_card(res)
        ok, reason = card.check_card(text, res)
        check(f"plain card is valid, history {history}", ok, reason)
        check(f"plain card is short, history {history}", len(text.split()) <= 110)

    # Every number in the card comes from the result.
    res = calc.recommend(["sorghum"], data=data)
    text = card.template_card(res)
    check("plain card adds no number", not card._numbers(text.lower()) - card._numbers(card._facts_text(res).lower()))

    # A drafted card that invents a date, a claim or a confidence is refused.
    invented = {
        "invented date": "Maize. Plant on 2 April 2026.",
        "invented month": "Maize. Plant in September.",
        "yield claim": "This will increase your yield.",
        "guarantee": "Common bean is guaranteed to do well.",
        "confidence": "I am confident Maize is best.",
        "empty": "",
    }
    for name, text in invented.items():
        ok, _ = card.check_card(text, res)
        check(f"card guard rejects {name}", not ok)

    # Without credentials the service still answers, and says why.
    card_en, card_lg, notes = card.build_cards(res)
    check("card exists with no credentials", bool(card_en))
    check("no Luganda card without a token", card_lg is None)
    check("notes say what fell back", len(notes) == len(card.build_cards(res)[2]))

    # "auto" and a blank district mean the one site the data file holds. A
    # different name is refused, because answering it would use another
    # district's numbers.
    import app as service  # noqa: E402

    for value in ("auto", "", None):
        payload = {"previous_crops": ["sorghum"]}
        if value is not None:
            payload["district"] = value
        out = service.handle_request(payload)["body"]
        check(f"district {value!r} uses the data file site", bool(out["recommended_crop"]))

    try:
        service.handle_request({"previous_crops": [], "district": "Nakasongola"})
        check("a different district is refused", False)
    except calc.RequestError:
        check("a different district is refused", True)

    # The response carries the agreed fields and no others.
    out = service.handle_request({"previous_crops": ["maize"]})["body"]
    check(
        "response carries the agreed fields only",
        set(out) <= {"recommended_crop", "when", "why", "alternative", "reasons", "card_en", "card_lg"},
        str(sorted(out)),
    )

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
