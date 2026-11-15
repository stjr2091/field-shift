"""Write a short card from a computed result, then translate it.

Two rules hold the honesty of this module:

1. The text is built from the result fields only. The language model is given
   those fields and told to phrase them. It is never asked a farming question.
2. Every card is checked against its own facts before it leaves. A number or a
   month that is not in the supplied fields rejects the draft, and the plain
   template is used instead. A model cannot add a figure, a date, a confidence
   claim or a success claim to a card.

Without credentials the plain template is used and the card still returns. The
service therefore answers from the data file alone.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
SUNBIRD_URL = "https://api.sunbird.ai/tasks/translate"

# Model names come from the pattern already in use for this vocabulary. The
# small model answers first and the larger one covers a refusal.
GROQ_MODEL = "openai/gpt-oss-120b"

# This model reasons before it writes, and the reasoning is billed to the token
# limit. At 300 tokens the whole budget went on thinking and the card came back
# empty. The ceiling is set well above the card length so the text always fits
# after the reasoning. The card itself is still held to 110 words by the check.
GROQ_MAX_TOKENS = 1200

# The provider refuses the default Python client signature, so the service names
# itself. Without this header the first call returns 403 and no card is written.
USER_AGENT = "field-shift-service/1.0"
GROQ_TIMEOUT_S = 12
SUNBIRD_TIMEOUT_S = 15

# Words that would turn a direction into a promise. A draft holding one is
# rejected, because the rules table holds no yield, no trial and no guarantee.
BANNED = [
    "yield", "harvest success", "guarantee", "guaranteed", "will increase",
    "ensure", "confident", "confidence", "best crop", "proven", "certified",
    "always does well", "always yield", "always good", "does well every",
]

# A crop may not be named unless it is in the facts for this request. The list
# is the crops a model or a translator might reach for, not a seed catalogue.
FOREIGN_CROPS = [
    "potato", "potatoes", "cassava", "rice", "wheat", "banana", "matooke",
    "sweet potato", "tomato", "onion", "coffee", "tea", "cotton", "tobacco",
    "soya", "soybean", "cowpea", "pigeon pea", "chickpea", "barley", "oats",
]

# Claims that a card may not make, in the plainest words. The Luganda card is
# not checked against a word list of its own: guessing Luganda spellings would
# invent the very vocabulary this module refuses. It is checked by translating
# it back to English and testing the English that comes out.


SYSTEM_PROMPT = """You rewrite a fixed agricultural result as a short card.
Rules:
1. Use only the fields given. Add no number, date, month, place, dose, price or measurement.
2. Copy the "when" value into the card word for word. Keep every month it names. Never replace the window with "early season", "the rains", "two seasons" or any other summary.
3. Add no advice, no recommendation of your own, and no new crop. Name the alternative exactly as the "alternative" field gives it.
4. Never mention yield, harvest success, profit, confidence, "always does well" or a guarantee.
5. State that the figure is district-scale. Never say national, country or regional.
6. Keep the direction of the reason as given. A favourable pair must not read as unfavourable.
7. If a "tie_line" field is present, include its meaning in the card. Say that the crops tie and that the order listed decided.
8. Plain text. No markdown, no bullets, no headings, no emoji.
9. At most 90 words. Seven short sentences at most.
10. Write for a farmer and an extension worker. Simple words, short sentences.
Return the card text only."""


def _facts_text(result: dict) -> str:
    """The exact fields a card may use, as one readable block."""
    facts = result.get("facts") or {}
    lines = [
        f"recommended_crop: {result.get('recommended_crop')}",
        f"when: {result.get('when')}",
        f"why: {result.get('why')}",
        f"alternative: {result.get('alternative')}",
    ]
    for reason in result.get("reasons", []):
        lines.append(f"reason: {reason}")
    for key in ("previous_crops", "site", "window_basis", "onset", "soil_ph", "moisture", "assumption"):
        if facts.get(key) not in (None, "", []):
            lines.append(f"{key}: {facts[key]}")
    if facts.get("tie_line"):
        # Given last and labelled, so the model treats it as a required line
        # rather than another sentence it may drop for length.
        lines.append(f"tie_line (must appear in the card): {facts['tie_line']}")
    if facts.get("unknown_rules"):
        lines.append(f"unknown_rules: {', '.join(facts['unknown_rules'])}")
    return "\n".join(lines)


def template_card(result: dict) -> str:
    """The plain card, built from the result fields with no model involved."""
    facts = result.get("facts") or {}
    parts = [
        f"{result['recommended_crop']}. Planting window: {result['when']}.",
        f"Why: {result['why']}",
    ]
    if facts.get("tie_line"):
        parts.append(str(facts["tie_line"]))
    parts.append(f"Alternative: {result['alternative']}.")
    if facts.get("unknown_rules"):
        names = ", ".join(facts["unknown_rules"]).replace("_", " ")
        parts.append(f"Not held for this crop: {names}.")
    parts.append("Rotation reasons give a direction only, not a measured amount.")
    parts.append("This is district-scale, not a field reading.")
    return " ".join(parts)


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", text))


def _months(text: str) -> set[str]:
    names = {
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    }
    return {word.lower() for word in re.findall(r"[A-Za-z]+", text) if word.lower() in names}


def _crop_words(result: dict) -> set[str]:
    """Every crop word a card may name for this request.

    A card may name the crop it recommends, the crops in the history, the
    alternative and the other tied crops, because those are the request's own
    facts. Anything else is a crop the answer did not come from.
    """
    facts = result.get("facts") or {}
    allowed = {result["recommended_crop"].lower(), str(result["alternative"]).lower()}
    for key in ("previous_crops", "tied_crops"):
        for name in facts.get(key) or []:
            allowed.add(str(name).replace("_", " ").lower())
    # The same crops as they are written in prose, e.g. "common bean".
    out = set()
    for name in allowed:
        out.update(name.split())
        out.add(name)
    return out


def check_card(card: str, result: dict) -> tuple[bool, str]:
    """Return (ok, reason). A card that fails is not sent.

    The check has two sides. A card may not add anything that is not in the
    facts, such as a number, a month, a crop or a claim. It also may not drop
    what the reader came for: the crop, the planting window, the alternative,
    the direction of the reason, and the tie disclosure when one occurred. A
    card that says "plant in the early season" instead of the published months
    has lost the answer, so it is refused like an invented one.
    """
    text = (card or "").strip()
    if not text:
        return False, "empty card"
    if len(text.split()) > 110:
        return False, "card is longer than the limit"
    lowered = text.lower()
    for word in BANNED:
        if word in lowered:
            return False, f"card holds a banned claim: {word}"

    # A scope word wider than the data breaks the district-scale claim.
    for word in ("national", "country-wide", "countrywide", "regional", "state-wide"):
        if word in lowered:
            return False, f"card widens the scale beyond district: {word}"

    allowed = _facts_text(result).lower()
    extra_numbers = _numbers(lowered) - _numbers(allowed)
    if extra_numbers:
        return False, f"card holds a number not in the facts: {sorted(extra_numbers)}"
    extra_months = _months(lowered) - _months(allowed)
    if extra_months:
        return False, f"card holds a month not in the facts: {sorted(extra_months)}"

    # An abbreviated month such as "Sep." hides a missing month behind a
    # different spelling, so a card that uses one is refused.
    for short in ("jan.", "feb.", "mar.", "apr.", "jun.", "jul.", "aug.", "sep.", "sept.", "oct.", "nov.", "dec."):
        if short in lowered:
            return False, f"card abbreviates a month: {short}"

    # A crop the request did not name is invented evidence.
    crops = _crop_words(result)
    for crop in FOREIGN_CROPS:
        if crop in lowered and crop not in crops:
            return False, f"card names a crop that is not in the facts: {crop}"

    # The crop must be named, so the card cannot be read as advice for another.
    crop_words = result["recommended_crop"].lower().split()
    if not all(word in lowered for word in crop_words):
        return False, f"card does not name the recommended crop: {result['recommended_crop']}"

    # The alternative must be the one the facts give, not another crop.
    alt = str(result["alternative"]).lower()
    if alt not in ("", "none held") and "alternative" in lowered and alt not in lowered:
        return False, f"card names a different alternative than the facts: {result['alternative']}"

    # Every month the window names must survive into the card. A window given
    # only as "early season" is not the published window.
    missing = _months(str(result["when"])) - _months(lowered)
    if missing:
        return False, f"card drops the planting window month(s): {sorted(missing)}"

    # A tie that the facts disclose must appear in the card. Otherwise the one
    # crop named reads as a finding when the order decided it.
    facts = result.get("facts") or {}
    if facts.get("tie_line"):
        if "tie" not in lowered and "order" not in lowered:
            return False, "card omits the tie disclosure"

    return True, "ok"


def groq_card(result: dict) -> tuple[str | None, str]:
    """Ask the model to phrase the supplied fields. Returns (card, note)."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None, "GROQ_API_KEY is not set, so the plain card was used."

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.1,
        "max_completion_tokens": GROQ_MAX_TOKENS,
        "reasoning_effort": "low",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Fields to phrase:\n" + _facts_text(result)},
        ],
    }
    request = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=GROQ_TIMEOUT_S) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return None, f"Groq returned HTTP {error.code}, so the plain card was used."
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        return None, f"Groq was not reachable ({type(error).__name__}), so the plain card was used."

    try:
        card = (body["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return None, "Groq returned no text, so the plain card was used."

    ok, reason = check_card(card, result)
    if not ok:
        return None, f"Groq card rejected ({reason}), so the plain card was used."
    return card, "Card phrased by the model from the supplied fields, then checked."


def check_luganda(card_lg: str, card_en: str, back_text: str, result: dict) -> tuple[bool, str]:
    """Return (ok, reason) for a translated card.

    Three things are tested, and each one is a defect a reviewer would catch:

    1. The window months survive. Sunbird keeps English month names, so the
       months in the English card must appear in the Luganda card. A dropped
       month means the window is not there.
    2. The meaning survives. The card is translated back to English and the
       result is read. A crop that appeared, a claim, a wider scope or a
       reversed direction is a meaning change, whatever the Luganda says.
    3. The length stays a card. A translation that doubles the text is not a
       card any more.

    A card that fails any test is dropped. An unverified translation is not
    better than none: the English card already carries the answer.
    """
    text = (card_lg or "").strip()
    if not text:
        return False, "empty Luganda card"

    if len(text.split()) > 160:
        return False, "Luganda card is longer than the limit"

    # 1. The months of the window must survive translation.
    missing = _months(card_en) - _months(text)
    if missing:
        return False, f"Luganda card drops the window month(s): {sorted(missing)}"

    # 2. The meaning, read from the round trip back to English.
    back = (back_text or "").strip().lower()
    if not back:
        return False, "no back-translation was returned, so the card is unverified"

    for word in BANNED:
        if word in back:
            return False, f"back-translation holds a banned claim: {word}"
    for word in ("national", "country", "countrywide", "regional", "nationwide"):
        if word in back:
            return False, f"back-translation widens the scale beyond district: {word}"

    crops = _crop_words(result)
    for crop in FOREIGN_CROPS:
        if crop in back and crop not in crops:
            return False, f"back-translation names a crop that is not in the facts: {crop}"

    # A favourable reason read as unusable is a reversed direction.
    facts = result.get("facts") or {}
    direction = str(facts.get("pair_direction") or "").lower()
    if direction == "for":
        for phrase in ("not a good idea", "should not", "avoid", "do not plant", "unfavourable", "unfavorable", "poor choice"):
            if phrase in back:
                return False, f"back-translation reverses a favourable direction: {phrase}"
    if direction == "against":
        for phrase in ("good idea", "recommended", "favourable", "favorable", "should follow"):
            if phrase in back:
                return False, f"back-translation reverses an unfavourable direction: {phrase}"

    # The window months must survive the round trip too, not only the first leg.
    back_missing = _months(card_en) - _months(back)
    if back_missing:
        return False, f"back-translation drops the window month(s): {sorted(back_missing)}"

    return True, "ok"


def sunbird_translate(text: str, source: str = "eng", target: str = "lug") -> tuple[str | None, str]:
    """Translate text. Returns (text, note).

    The same call serves both directions, so the card out and the round trip
    back use one code path. A difference between them would make the check
    meaningless.
    """
    token = os.environ.get("SUNBIRD_API_TOKEN", "").strip()
    if not token:
        return None, "SUNBIRD_API_TOKEN is not set, so no Luganda card was made."

    payload = {"source_language": source, "target_language": target, "text": text}
    request = urllib.request.Request(
        SUNBIRD_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=SUNBIRD_TIMEOUT_S) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return None, f"Sunbird returned HTTP {error.code}, so no Luganda card was made."
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        return None, f"Sunbird was not reachable ({type(error).__name__}), so no Luganda card was made."

    payload_out = body.get("output") if isinstance(body.get("output"), dict) else body
    translated = (payload_out or {}).get("translated_text") or ""
    translated = translated.strip()
    if not translated or (payload_out or {}).get("Error"):
        return None, "Sunbird returned no usable text, so no Luganda card was made."
    if payload_out.get("target_language") not in (None, target):
        return None, f"the translator returned {payload_out.get('target_language')}, not {target}, so the text was dropped."
    return translated, f"translated {source} to {target}."


def build_cards(result: dict) -> tuple[str, str | None, list[str]]:
    """Return (card_en, card_lg_or_none, notes). Notes say what each step did."""
    notes: list[str] = []
    card, note = groq_card(result)
    if card is None:
        card = template_card(result)
    notes.append(note)

    ok, reason = check_card(card, result)
    if not ok:
        card = template_card(result)
        notes.append(f"Draft rejected ({reason}), plain card used.")

    # The English card is final at this point. The Luganda card is a copy of it
    # and must prove it says the same thing before it is sent.
    translated, note = sunbird_translate(card)
    notes.append(note)
    if translated is None:
        return card, None, notes

    back, note = sunbird_translate(translated, source="lug", target="eng")
    notes.append(f"round trip back: {note}")
    if back is None:
        notes.append("Luganda card dropped: it could not be read back, so it is unverified.")
        return card, None, notes

    ok, reason = check_luganda(translated, card, back, result)
    if not ok:
        notes.append(f"Luganda card dropped: {reason}.")
        return card, None, notes

    notes.append("Luganda card passed the month and round-trip check.")
    return card, translated, notes
