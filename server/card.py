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
]

SYSTEM_PROMPT = """You rewrite a fixed agricultural result as a short card.
Rules:
1. Use only the fields given. Add no number, date, month, place, dose, price or measurement.
2. Copy the "when" value into the card word for word. Keep every month it names. Never replace the window with "early season", "the rains" or any other summary.
3. Add no advice, no recommendation of your own, and no new crop.
4. Never mention yield, harvest success, profit, confidence or a guarantee.
5. State that the figure is district-scale, and that rotation reasons are direction only.
6. Plain text. No markdown, no bullets, no headings, no emoji.
7. At most 90 words. Six short sentences at most.
8. Write for a farmer and an extension worker. Simple words, short sentences.
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
    if facts.get("unknown_rules"):
        lines.append(f"unknown_rules: {', '.join(facts['unknown_rules'])}")
    return "\n".join(lines)


def template_card(result: dict) -> str:
    """The plain card, built from the result fields with no model involved."""
    facts = result.get("facts") or {}
    parts = [
        f"{result['recommended_crop']}. Planting window: {result['when']}.",
        f"Why: {result['why']}",
        f"Alternative: {result['alternative']}.",
    ]
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


def check_card(card: str, result: dict) -> tuple[bool, str]:
    """Return (ok, reason). A card that fails is not sent.

    The check has two sides. A card may not add anything that is not in the
    facts, such as a number, a month or a claim. It also may not drop the two
    things the reader came for: the crop and the planting window. A card that
    says "plant in the early season" instead of the published months has lost
    the answer, so it is refused like an invented one.
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
    allowed = _facts_text(result).lower()
    extra_numbers = _numbers(lowered) - _numbers(allowed)
    if extra_numbers:
        return False, f"card holds a number not in the facts: {sorted(extra_numbers)}"
    extra_months = _months(lowered) - _months(allowed)
    if extra_months:
        return False, f"card holds a month not in the facts: {sorted(extra_months)}"

    # The crop must be named, so the card cannot be read as advice for another.
    crop_words = result["recommended_crop"].lower().split()
    if not all(word in lowered for word in crop_words):
        return False, f"card does not name the recommended crop: {result['recommended_crop']}"

    # Every month the window names must survive into the card. A window given
    # only as "early season" is not the published window.
    missing = _months(str(result["when"])) - _months(lowered)
    if missing:
        return False, f"card drops the planting window month(s): {sorted(missing)}"
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


def sunbird_translate(text: str) -> tuple[str | None, str]:
    """Translate English to Luganda. Returns (text, note)."""
    token = os.environ.get("SUNBIRD_API_TOKEN", "").strip()
    if not token:
        return None, "SUNBIRD_API_TOKEN is not set, so no Luganda card was made."

    payload = {"source_language": "eng", "target_language": "lug", "text": text}
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
    if payload_out.get("target_language") not in (None, "lug"):
        return None, "Sunbird returned a language other than Luganda, so it was dropped."
    return translated, "Luganda card translated by Sunbird from the English card."


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

    translated, note = sunbird_translate(card)
    notes.append(note)
    return card, translated, notes
