"""Checks for the recommendation service. No network, no credentials.

    python server/test_recommend.py

Each check states what must hold. A failure prints the case and exits non-zero,
so this can run in a release check.
"""

from __future__ import annotations

import re
import sys
from datetime import date as _date
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

    # A card that drops the published window, or the crop name, is refused. The
    # reader came for those two things, so losing them is a failed card.
    # A crop is dropped, or the window is replaced, or a direction is turned.
    # The request pins the first rains, so the fixture card carries the
    # window that request was audited against.
    bean = calc.recommend(["maize"], soil_ph=6.1, planting_date="2026-03-10", data=data)
    dropped = {
        "window replaced by a season word": "Common bean. Plant in the early season.",
        "crop name missing": "Plant in March to mid-April or mid-August to December.",
    }
    for name, text in dropped.items():
        ok, reason = card.check_card(text, bean)
        check(f"card guard rejects {name}", not ok, reason)

    # The five English drafts that slipped past the first check. Each is a
    # different way to change the answer while looking like a card. The
    # requests pin the first rains with an explicit date, so the fixtures read
    # the windows those cards were audited against.
    tie_case = calc.recommend(["sorghum"], planting_date="2026-03-10", data=data)
    slipped = {
        "an invented crop": ("Maize. Planting window: 15 March to 15 August. Also potatoes.", tie_case),
        "an abbreviated month": ("Maize. Planting window: 15 March to Sep.", tie_case),
        "a season summary for the window": ("Maize. Two seasons. Alternative: Common bean.", tie_case),
        "a different alternative crop": ("Maize. Planting window: 15 March to 15 August. Cassava is the alternative.", tie_case),
        "a success claim": ("Maize. Planting window: 15 March to 15 August. Always does well.", tie_case),
        "a wider scale": ("Maize. Planting window: 15 March to 15 August. A national figure.", tie_case),
        "a reversed direction": ("Plant Common bean after maize. This is not a good idea.", bean),
    }
    for name, (text, target) in slipped.items():
        ok, reason = card.check_card(text, target)
        check(f"card guard rejects {name}", not ok, reason)

    # A tie must reach both cards. The plain card carries it, and a card that
    # leaves it out is refused.
    check("a tie is disclosed in the facts", bool(tie_case["facts"].get("tie_line")))
    check(
        "the tie names every tied crop",
        all(name in tie_case["facts"]["tie_line"] for name in tie_case["facts"]["tied_crops"]),
    )
    plain_tie = card.template_card(tie_case)
    check("the plain card shows the tie", "tie" in plain_tie.lower() and "order" in plain_tie.lower())
    ok, reason = card.check_card(plain_tie, tie_case)
    check("the plain card with a tie passes", ok, reason)
    ok, reason = card.check_card("Maize. Planting window: 15 March to 15 August.", tie_case)
    check("a card that omits the tie is refused", not ok, reason)

    # No tie, no tie sentence. A card is never told to claim one.
    no_tie = calc.recommend(["maize"], data=data)
    check("no tie is claimed when none occurred", not no_tie["facts"].get("tie_line"))

    # Fixtures from the second audit. Each card below was accepted once, and
    # each must now be refused.

    # A favourable pair read as unusable. The whole defect is one word. The
    # request pins the first rains, so the fixtures carry the window that
    # request was audited against.
    favour = calc.recommend(["maize"], planting_date="2026-03-10", data=data)
    check(
        "the maize pair is held to be favourable",
        favour["facts"].get("pair_direction") == "for",
        str(favour["facts"].get("pair_direction")),
    )
    favour_en = (
        "Plant Common bean. Planting window: March to mid-April. Maize before "
        "Common bean is neutral to favourable. The first rains start about "
        "18 March; this figure is district-scale."
    )
    favour_back = (
        "Plant Common bean. Planting window: March to mid-April. Planting maize "
        "after common bean is not suitable. The first rains start about "
        "18 March; this figure is district-scale."
    )
    ok, reason = card.check_card(favour_back, favour)
    check("card guard rejects a favourable pair read as unsuitable", not ok, reason)
    ok, reason = card.check_luganda(favour_en, favour_en, favour_back, favour)
    check("Luganda guard rejects a reversal with no listed phrase", not ok, reason)

    # A made-up crop word that the translator renders as an allowed crop. The
    # rendering changes between calls: the same Luganda word has come back as
    # "maize" and, in the round trip the audit read, as "beans". The fixture
    # holds the "beans" rendering, because the card names common bean once and
    # that rendering names a bean crop three times. The request pins the first
    # rains, so the fixture card carries the window it was audited against.
    made_up = calc.recommend(["sorghum"], planting_date="2026-03-10", data=data)
    made_up_en = (
        "Maize is the recommended crop. Planting window: 15 March to 15 August. "
        "The previous crop was sorghum and no rotation rule is held for maize after "
        "sorghum; the reason is direction only. An alternative is common bean. The "
        "first rains timing is a district-scale figure. This advice applies to Soroti."
    )
    made_up_back = (
        "The best planting time is for beans. Planting season: 15th March to 15th "
        "August. The first crop was sorghum and there were no rules about replanting "
        "beans after sorghum; the reason being only one crop can be planted at a "
        "time. Another option is common bean. The start of the first rains is on a "
        "district basis. This advice applies to Soroti."
    )
    ok, reason = card.check_luganda(made_up_en, made_up_en, made_up_back, made_up)
    check("Luganda guard rejects a made-up crop that renders as an allowed crop", not ok, reason)

    # The same defect under a rendering that agrees with the card. The made-up
    # word then reads back as the recommended crop and the counts match, so
    # the Luganda card itself must name the crop. This is the Luganda text the
    # audit held, and it names neither the Luganda nor the English crop name.
    made_up_lg = (
        "Obusimba obulungi bwe bulimi bw\u2019obumonde. Ekiseera ky\u2019okusimba: 15 March "
        "okutuuka 15 August. Obusimba obwasooka bwali sorghum era tewali mateeka ga kuddamu "
        "kusimba bumonde oluvannyuma lwa sorghum; ensonga eri mu ngeri yokka. Ekyokulondako "
        "ekirala kye common bean. Okutandika kw\u2019enkuba eyasooka kuli ku mutendera gwa "
        "disitulikiti. Amagezi gano gakozesebwa ku Soroti."
    )
    ok, reason = card.check_luganda(made_up_lg, made_up_en, made_up_en, made_up, crop_lg="kasooli")
    check("Luganda guard rejects a card that never names the recommended crop", not ok, reason)

    # Fail closed. The crop name comes from a live lookup, and the window
    # where that lookup cannot confirm a name is exactly where an invented
    # crop word hides. A lookup that was judged but not confirmed drops the
    # card; a lookup that never ran, because no token is set, does not.
    saved_lookup = card.luganda_crop_name
    try:
        card.luganda_crop_name = lambda crop: (None, True)
        ok, reason = card.check_luganda(made_up_en, made_up_en, made_up_en, made_up)
        check("Luganda guard fails closed when the crop name cannot be confirmed", not ok, reason)
        card.luganda_crop_name = lambda crop: (None, False)
        ok, reason = card.check_luganda(made_up_en, made_up_en, made_up_en, made_up)
        check("Luganda guard skips the name check when no lookup was possible", ok, reason)
    finally:
        card.luganda_crop_name = saved_lookup

    # A genuine card still passes when the lookup confirms the name.
    ok, reason = card.check_luganda(made_up_en, made_up_en, made_up_en, made_up, crop_lg="kasooli")
    check("a genuine Luganda card passes when the crop name is confirmed", ok, reason)

    # A confirmed name may hold several words. The card must carry that
    # phrase or the English name; a card that holds neither still drops.
    bean_result = calc.recommend(["maize"], data=data)
    bean_phrase = "ebikoola by'ebijanjaalo ebya bulijjo"
    bean_card_with = "Okusimba " + bean_phrase + ". Ekiseera ky'okusimba kiri mu March na April."
    bean_card_without = "Okusimba ebirime ebirala. Ekiseera ky'okusimba kiri mu March na April."
    saved_lookup = card.luganda_crop_name
    try:
        card.luganda_crop_name = lambda crop: (bean_phrase, True)
        ok, reason = card.check_luganda(bean_card_with, bean_card_with, bean_card_with, bean_result)
        check("a multi-word confirmed name passes a card that holds it", ok, reason)
        ok, reason = card.check_luganda(bean_card_without, bean_card_without, bean_card_without, bean_result)
        check("a card without the confirmed multi-word name drops", not ok, reason)
    finally:
        card.luganda_crop_name = saved_lookup

    # A tie line on a history that holds no tie. The first rains are pinned,
    # so the fixture reads the window that history was audited against.
    two_crops = calc.recommend(["maize", "common_bean"], planting_date="2026-03-10", data=data)
    check("the two-crop history holds no tie", not two_crops["facts"].get("tie_line"))
    false_tie = (
        "When: 15 March to 15 August. Maize is recommended. Planting window is 15 "
        "March to 15 August. The first rains usually start in mid-March, a "
        "district-scale observation. Common bean before Maize is favourable. "
        "Alternative crop is Finger millet. The crops tie and the "
        "order listed decided. The season assumed is the first rains season."
    )
    ok, reason = card.check_card(false_tie, two_crops)
    check("card guard rejects a tie the facts do not hold", not ok, reason)

    # Fault: the season pick was silent. The response and the card must both
    # state it, with the data fact that governs it. With no date, today's
    # date picks the season, and the sentence names the pick it made.
    for today, expected in (
        (_date(2026, 3, 10), "first rains"),
        (_date(2026, 11, 15), "second rains"),
    ):
        res = calc.recommend(["sorghum"], today=today, data=data)
        line = res.get("season_assumption") or ""
        check(
            f"season assumption names the pick for {today}",
            expected in line and "today's date" in line and "No planting date was entered" in line,
            line,
        )
        check(
            f"season assumption sits in the facts for {today}",
            res["facts"].get("season_assumption") == line,
        )
    season_case = calc.recommend(["sorghum"], planting_date="2026-03-10", data=data)
    plain_season = card.template_card(season_case)
    check("the plain card carries the season assumption word for word", season_case["facts"]["season_assumption"] in plain_season)
    no_season = "Plant Maize. Planting window: 15 March to 15 August. No rotation rule is held for Maize after Sorghum; the pair is unknown. Several crops tie on the rules held, so the listed order decided. Alternative crop: Common bean. This is district-scale advice, not a field reading."
    ok, reason = card.check_card(no_season, season_case)
    check("card guard rejects a card that omits the season assumption", not ok, reason)

    # Fault: the plain card is the primary card. It speaks to the farmer,
    # carries one idea per sentence, and is the card sent without credentials.
    for history in ([], ["maize"], ["common_bean"], ["sorghum"]):
        target = calc.recommend(history, data=data)
        plain = card.template_card(target)
        check(f"the plain card opens with an instruction for {history}", plain.startswith("Plant "), plain[:40])
        check(f"the plain card holds five sentences or fewer for {history}",
              len([s for s in re.split(r"(?<=[.!?])\s+", plain) if s.strip()]) <= 5, plain)
        ok, reason = card.check_card(plain, target)
        check(f"the plain card passes its own guard for {history}", ok, reason)
    card_en, card_lg, notes = card.build_cards(season_case)
    check("the card sent with no credentials is the plain card", card_en == card.template_card(season_case))

    # Fault: prompt echo and talk about the tool. Neither belongs in a card.
    echoes = {
        "an instruction line": "You rewrite a fixed agricultural result as a short card. Plant Maize from 15 March to 15 August. Season assumed: first rains. This is district-scale advice.",
        "the rules header": "Rules: plant Maize from 15 March to 15 August. Season assumed: first rains. This is district-scale advice.",
        "the word system": "The system holds Maize. Planting window: 15 March to 15 August. Season assumed: first rains. This is district-scale advice.",
        "third-person talk": "The recommendation is Maize. Planting window: 15 March to 15 August. Season assumed: first rains. This is district-scale advice.",
        "the tool speaks": "The tool recommends Maize. Planting window: 15 March to 15 August. Season assumed: first rains. This is district-scale advice.",
    }
    for name, text in echoes.items():
        ok, reason = card.check_card(text, season_case)
        check(f"card guard rejects {name}", not ok, reason)

    # Fault: the last grown crop is never advised again, neither as the crop
    # nor as the alternative. Checked over every history of up to two crops.
    crop_keys = ["maize", "common_bean", "finger_millet", "sorghum", "groundnut"]
    histories = [[]] + [[c] for c in crop_keys] + [list(p) for p in __import__("itertools").product(crop_keys, repeat=2)]
    guard_ok = True
    guard_detail = ""
    for history in histories:
        res = calc.recommend(history, data=data)
        last = history[-1] if history else None
        if last:
            if res["recommended_crop"].lower().replace(" ", "_") == last:
                guard_ok, guard_detail = False, f"{history} recommended the last crop"
            alt_key = str(res["alternative"]).lower().replace(" ", "_")
            if alt_key == last:
                guard_ok, guard_detail = False, f"{history} offered the last crop as alternative"
            if "last crop" not in " ".join(res["reasons"]):
                guard_ok, guard_detail = False, f"{history} does not state the monocrop guard"
    check("no history is advised its last crop again", guard_ok, guard_detail)

    # The cards that audit kept must stay kept on the checks that audit was
    # about: crops, direction and tie. The contract has since gained the
    # season assumption, so a card that omits that line is now incomplete,
    # and that omission is the only refusal these old cards may earn. Each
    # request pins the first rains with an explicit date, the season those
    # cards were audited under, and the first card's alternative window now
    # names the first rains only, because a chosen-season request shows the
    # chosen season's window.
    kept = [
        (["sorghum"], None, None, "Plant Maize. Planting window: 15 March to 15 August. No rotation rule after sorghum, the pair is unknown. First rains start about 18 March, district-scale figure. The crops tie, no rule separated them, so the list order decided. Alternative crop is Common bean. Alternative window: March to mid-April."),
        ([], None, None, "Maize is recommended. Planting window: 15 March to 15 August. The first rains start about 18 March, a district-scale figure. No previous crop was given, so rotation was not judged. The crops tie and the list order decided. Alternative crop is Common bean. This is a district-scale recommendation."),
        (["groundnut"], 5.0, None, "Plant Maize from 15 March to 15 August. No rotation rule exists after groundnut, and the pair is unknown. Soil pH 5.0 is outside Maize's sourced range, making it a less-good match. The first rains usually begin around 18 March, a district-scale figure. The crops tie, so the listed order decided. Alternative is Common bean. Common bean also has no rotation rule after groundnut."),
        (["finger_millet"], 6.4, "moist", "Plant Maize. Planting window: 15 March to 15 August. Soil pH 6.4 fits the range for Maize. The first rains usually start about 18 March, a district-scale figure. The crops tie; no rule separates them, so the list order decided. Alternative crop is Common bean. No rotation rule is held for Maize after Finger millet."),
    ]
    for history, ph, wet, text in kept:
        target = calc.recommend(history, soil_ph=ph, moisture=wet, planting_date="2026-03-10", data=data)
        ok, reason = card.check_card(text, target)
        kept_ok = ok or reason.startswith("card omits the season assumption")
        check(f"audited card for {history} keeps its facts", kept_ok, reason)

    # One audited card offered the last grown crop again as the alternative.
    # The monocrop guard now refuses that at the ranking, so the card no
    # longer matches the facts, and the facts state why.
    maize_card = "Common bean. Planting window: March to mid-April, or mid-August to December. Why: Maize before Common bean is neutral to favourable. This is a direction only, with no measured number. Alternative: Maize. Not held for this crop: planting rainfall threshold. Rotation reasons give a direction only, not a measured amount. This is district-scale, not a field reading."
    again = calc.recommend(["maize"], data=data)
    ok, reason = card.check_card(maize_card, again)
    check("card guard rejects the last grown crop as the alternative", not ok, reason)
    check("the facts state the monocrop guard", "last crop" in str(again["facts"].get("last_crop_guard")), str(again["facts"].get("last_crop_guard")))

    # A translated card is checked too. An unverified translation is dropped.
    en = card.template_card(bean)
    lg_text = (
        "Ebikoola bya Common bean. Ekiseera ky'okusimba: Okuva mu March okutuuka "
        "wakati wa April. Season: February to May. Ekyokulondako: Maize. "
        "Kino kya disitulikiti."
    )
    lg_back = (
        "Common bean. Planting window: March to mid-April. Season: February to "
        "May. Alternative: Maize. This is district-scale."
    )
    ok, reason = card.check_luganda(lg_text, en, lg_back, bean)
    check("a faithful Luganda card passes", ok, reason)

    lg_defects = {
        "an invented crop in the translation": (
            lg_text, "Common bean. Window March to mid-April. Also potatoes. district-scale."
        ),
        "a national claim in the translation": (
            lg_text, "Common bean. Window March to mid-April. A national figure."
        ),
        "a reversed direction in the translation": (
            lg_text, "Common bean. Window March to mid-April. Maize before it is not a good idea."
        ),
        "a dropped window month": (
            "Ebikoola bya Common bean. Kino kya disitulikiti.", lg_back
        ),
        "a yield claim in the translation": (
            lg_text, "Common bean. Window March to mid-April. This gives high yield."
        ),
        "no back-translation at all": (lg_text, ""),
    }
    for name, (text, back) in lg_defects.items():
        ok, reason = card.check_luganda(text, en, back, bean)
        check(f"Luganda guard rejects {name}", not ok, reason)

    # A dropped Luganda card is reported, never shipped silently.
    notes_text = " ".join(
        card.build_cards(bean)[2]
    )
    check("the card notes say what each step did", bool(notes_text.strip()))

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
        set(out) <= {"recommended_crop", "when", "why", "alternative", "reasons", "card_en", "card_lg", "season_assumption"},
        str(sorted(out)),
    )
    line = out.get("season_assumption", "")
    check(
        "response states the season pick and its basis",
        "today's date" in line and "season" in line and "No planting date was entered" in line,
        line,
    )

    # GET /assumption returns the same sentence, with no model call. With no
    # input it answers for the no-date default: today's date picks the season.
    assumption = service.assumption_response()["season_assumption"]
    check("the assumption endpoint returns the same sentence", assumption == out["season_assumption"])
    check("the assumption endpoint answers the no-date default", "today's date" in assumption, assumption)

    # The date contract. One optional planting_date picks the season; the
    # windows shown are that season's; the ranking and the guards run
    # unchanged. The boundary dates sit on both sides of both windows.
    pick_cases = [
        ("2026-01-31", "first_rains"),   # before the first window: next to come
        ("2026-02-01", "first_rains"),   # first day inside the first window
        ("2026-05-31", "first_rains"),   # last day inside the first window
        ("2026-06-01", "second_rains"),  # between the windows: next to come
        ("2026-07-31", "second_rains"),
        ("2026-08-01", "second_rains"),  # first day inside the second window
        ("2026-11-30", "second_rains"),  # last day inside the second window
        ("2026-12-01", "first_rains"),   # after both windows: next year's first
    ]
    for day_text, expected in pick_cases:
        row, _ = calc.pick_season(data, calc.normalise_planting_date(day_text))
        got = (row or {}).get("season")
        check(f"date {day_text} picks the {expected}", got == expected, str(got))

    for bad in ("2026-13-01", "20 August 2026", "2026-8-2", "20260820", "2026-02-30"):
        try:
            calc.normalise_planting_date(bad)
            check(f"a bad planting date is refused: {bad}", False)
        except calc.RequestError:
            check(f"a bad planting date is refused: {bad}", True)

    # A date inside the second season gives the second window, and says so.
    aug = calc.recommend(["maize"], planting_date="2026-08-20", data=data)
    line = aug["season_assumption"]
    check(
        "a dated request names the season and the date",
        "second rains" in line and "20 August 2026" in line,
        line,
    )
    check("the dated advice shows the second-season window", aug["when"] == "mid-August to December", aug["when"])
    check("the dated assumption sits in the facts", aug["facts"].get("season_assumption") == line)
    ok, reason = card.check_card(card.template_card(aug), aug)
    check("the plain card passes for a dated request", ok, reason)

    # A crop with no sourced window for the chosen season says so. It is
    # never shown the other season's window instead.
    maize_aug = calc.recommend([], planting_date="2026-08-20", data=data)
    check(
        "a crop with no second-season window says so",
        "no sourced planting window" in maize_aug["when"],
        maize_aug["when"],
    )
    check(
        "the no-window basis names the season",
        "second rains" in maize_aug["facts"]["window_basis"],
        maize_aug["facts"]["window_basis"],
    )

    # A date between the seasons is told what was chosen and why.
    june = calc.recommend(["maize"], planting_date="2026-06-15", data=data)
    check(
        "a between-seasons date names the next season",
        "next season to come" in june["season_assumption"] and "second rains" in june["season_assumption"],
        june["season_assumption"],
    )

    # The guards run unchanged for a dated request. A dated request that
    # holds no tie refuses a card that claims one.
    two = calc.recommend(["maize", "common_bean"], planting_date="2026-08-20", data=data)
    check("a dated two-crop request holds no tie", not two["facts"].get("tie_line"))
    ok, reason = card.check_card(card.template_card(two) + " The crops tie.", two)
    check("a dated card that claims a false tie is refused", not ok, reason)

    # The route accepts the optional date, refuses a bad one, and reads a
    # blank one as no date.
    out = service.handle_request({"previous_crops": [], "planting_date": "2026-08-20"})["body"]
    check("the route accepts a planting date", "second rains" in out["season_assumption"], out["season_assumption"])
    blank = service.handle_request({"previous_crops": [], "planting_date": "   "})["body"]
    check("a blank planting date means today", "today's date" in blank["season_assumption"], blank["season_assumption"])
    try:
        service.handle_request({"previous_crops": [], "planting_date": "20 August 2026"})
        check("the route refuses a bad planting date", False)
    except calc.RequestError:
        check("the route refuses a bad planting date", True)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
