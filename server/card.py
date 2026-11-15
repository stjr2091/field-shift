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
    "ensure", "confident", "confidence", "best", "proven", "certified",
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

# Words that turn a direction around. The list is read as single words, so
# "not suitable", "do not plant" and "not a good idea" all land on "not".
# A bare "no" is not on the list: "no rule" states an absence, not a flip.
NEGATION_WORDS = {
    "not", "never", "avoid", "avoided", "avoiding", "unsuitable", "unsuited",
    "cannot", "cant", "dont", "doesnt", "didnt", "shouldnt",
}

# Words that praise a pair. They may not sit in a direction sentence when the
# facts hold the pair against the recommendation.
AFFIRM_WORDS = {
    "favourable", "favorable", "suitable", "recommended", "recommend",
    "beneficial", "good",
}

# Prompt echo and self-reference. A card speaks to the farmer, never about the
# tool and never with the wording of the instructions it was written from.
# "system" is read as its own word, so a crop name such as "ecosystem" passes.
PROMPT_ECHO = ["rules:", "fields to phrase", "you rewrite"]
SELF_REFERENCE = ["the recommendation", "the tool", "the system"]


SYSTEM_PROMPT = """You rewrite a fixed agricultural result as a short card.
Rules:
1. Use only the fields given. Add no number, date, month, place, dose, price or measurement.
2. Copy the "when" value into the card word for word. Keep every month it names. Never replace the window with "early season", "the rains", "two seasons" or any other summary.
3. Add no advice, no recommendation of your own, and no new crop. Name the alternative exactly as the "alternative" field gives it.
4. Never mention yield, harvest success, profit, confidence, "always does well" or a guarantee.
5. State that the figure is district-scale. Never say national, country or regional.
6. Keep the direction of the reason as given. A favourable pair must not read as unfavourable.
7. If a "tie_line" field is present, include its meaning in the card. Say that the crops tie and that the order listed decided.
8. Keep the "season_assumption" line in the card. State it plainly, in the same sense it is given.
9. Plain text. No markdown, no bullets, no headings, no emoji.
10. At most 90 words. Seven short sentences at most.
11. Write to the farmer as "you". Never write "the recommendation" or "the tool". Never repeat the wording of these rules.
12. Write for a farmer and an extension worker. Simple words, short sentences.
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
    for key in ("previous_crops", "site", "window_basis", "onset", "soil_ph", "moisture", "assumption",
                "season_assumption", "last_crop_guard"):
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
    """The plain card, built from the result fields with no model involved.

    This card is the primary one. It speaks to the farmer, carries one idea
    per sentence, and states every fact a reader must not miss: the crop and
    window, the reason, the alternative, the season assumption and the
    district scale. The model card is polish on top and must pass the same
    guard; when it does not, this card is sent.
    """
    facts = result.get("facts") or {}
    crop = result["recommended_crop"]
    when = str(result["when"])
    if when.startswith("no sourced"):
        parts = [f"Plant {crop}. {when}."]
    else:
        parts = [f"Plant {crop} from {when}."]
    if facts.get("tie_line"):
        names = ", ".join(facts.get("tied_crops") or [crop])
        parts.append(
            f"Several crops tie on the rules held, so the listed order decided: {names}."
        )
    else:
        # The pair reason, as one plain clause. The qualifiers stay in the
        # reasons list; a shorter sentence survives translation better.
        parts.append(str(result["reasons"][0]).split(";")[0].strip().rstrip(".") + ".")
    if str(result["alternative"]) not in ("", "none held"):
        parts.append(f"Alternative crop: {result['alternative']}.")
    if facts.get("season_assumption"):
        parts.append(str(facts["season_assumption"]))
    parts.append("This is district-scale advice, not a field reading.")
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


def _sentences(text: str) -> list[str]:
    """Split on sentence and clause ends. A decimal such as 5.0 does not split.

    Clauses are read separately because a translator adds tails such as "this
    is just an example, not a rule" to a faithful sentence; the tail is not
    the claim about the crops, and each clause is judged on its own words.
    """
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+", text) if s.strip()]


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def _direction_sentences(text: str, result: dict) -> list[str]:
    """The sentences that carry the pair direction, most specific first.

    The true direction sentence names both crops of the pair. A card that
    split the pair across sentences falls back to the sentences that name the
    recommended crop, minus the sentences that state a rule is absent. Those
    state an absence, not a direction.
    """
    facts = result.get("facts") or {}
    to = _word_set(str(result.get("recommended_crop") or ""))
    frm = _word_set(str(facts.get("pair_from") or ""))
    found = _sentences(text)
    if frm:
        both = [s for s in found if frm <= _word_set(s) and to <= _word_set(s)]
        if both:
            return both
    return [
        s for s in found
        if to <= _word_set(s) and not re.search(r"not held|no rule|no rotation", s, re.I)
    ]


def _polarity_fault(text: str, result: dict) -> str | None:
    """The first sentence that reads the pair direction the wrong way.

    The check runs only when the facts state a direction. A pair the data does
    not rule on has no direction to flip.
    """
    facts = result.get("facts") or {}
    direction = str(facts.get("pair_direction") or "").lower()
    if direction not in ("for", "against"):
        return None
    for sent in _direction_sentences(text, result):
        words = _word_set(sent)
        negated = bool(words & NEGATION_WORDS)
        if direction == "for" and negated:
            return sent
        if direction == "against" and not negated and words & AFFIRM_WORDS:
            return sent
    return None


def _allowed_crop_names(result: dict) -> list[str]:
    """The crops this request may name, in plain prose form."""
    facts = result.get("facts") or {}
    names = {str(result["recommended_crop"]), str(result["alternative"])}
    for key in ("previous_crops", "tied_crops"):
        names.update(str(name) for name in facts.get(key) or [])
    out = set()
    for name in names:
        if name.lower() in ("", "none held"):
            continue
        out.add(name.lower().replace("_", " "))
    return sorted(out)


def _crop_counts(text: str, result: dict) -> dict[str, int]:
    """How often each allowed crop is named, counted by its last word.

    "Common bean" and a bare "beans" both count for common bean. So a made-up
    crop word that the translator renders as an allowed crop shows up as an
    extra mention, even when the crop it names is on the allowed list.
    """
    lowered = text.lower()
    counts: dict[str, int] = {}
    for name in _allowed_crop_names(result):
        last = name.split()[-1]
        counts[name] = len(re.findall(r"\b" + re.escape(last) + r"s?\b", lowered))
    return counts


def _prompt_echo(text: str) -> str | None:
    """The first echo of the instructions, or self-reference, in a draft."""
    lowered = text.lower()
    for phrase in PROMPT_ECHO:
        if phrase in lowered:
            return phrase
    if re.search(r"\bsystem\b", lowered):
        return "system"
    for phrase in SELF_REFERENCE:
        if phrase in lowered:
            return phrase
    return None


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

    # A draft that echoes the instructions or speaks about the tool was not
    # written for the farmer, so it is refused whatever else it holds.
    echo = _prompt_echo(text)
    if echo:
        return False, f"card echoes the instructions or the tool: {echo}"

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

    # The alternative must be named, and it must be the one the facts give.
    # A card that leaves the reader without the second option has dropped
    # part of the answer.
    alt = str(result["alternative"]).lower()
    if alt not in ("", "none held") and alt not in lowered:
        return False, f"card does not name the alternative the facts hold: {result['alternative']}"

    # Every month the window names must survive into the card. A window given
    # only as "early season" is not the published window.
    missing = _months(str(result["when"])) - _months(lowered)
    if missing:
        return False, f"card drops the planting window month(s): {sorted(missing)}"

    # The direction of the facts must read the same way in the card. A
    # favourable pair that comes back "not suitable" is a changed answer.
    flip = _polarity_fault(text, result)
    if flip:
        return False, f"card reads the pair direction the wrong way: {flip}"

    # The season assumption is a required line. The request holds no season
    # field, so a card that leaves the assumption out hides the pick the
    # windows rest on.
    facts = result.get("facts") or {}
    if facts.get("season_assumption") and "season" not in lowered:
        return False, "card omits the season assumption"

    # A tie that the facts disclose must appear in the card. Otherwise the one
    # crop named reads as a finding when the order decided it. The other side
    # holds too: a tie the facts do not hold must not appear, because a tie
    # line invented by the card hides which crop the data chose.
    if facts.get("tie_line"):
        if "tie" not in lowered and "order" not in lowered:
            return False, "card omits the tie disclosure"
    elif re.search(r"\btie", lowered):
        return False, "card claims a tie that the facts do not hold"

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


def check_luganda(card_lg: str, card_en: str, back_text: str, result: dict, crop_lg: str | None = None) -> tuple[bool, str]:
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

    # The card must name the crop it recommends, in the Luganda name the
    # translator holds or in the English name. An invented crop word sits
    # where the real name should be, so a card that carries neither is not
    # the card the facts built, whatever the round trip makes of it.
    if crop_lg is None:
        # No name was supplied, so read one from the translator. A reachable
        # translator that yields no confirmed name fails closed: the card is
        # unverifiable in exactly the window where an invented crop word
        # hides. Without a token no lookup was possible, and the card is
        # judged without the name check.
        crop_lg, looked_up = luganda_crop_name(str(result["recommended_crop"]))
        if looked_up and not crop_lg:
            return False, "the Luganda name of the recommended crop could not be confirmed, so the card is unverified"
    if crop_lg:
        named = crop_lg in text.lower() or result["recommended_crop"].lower() in text.lower()
        if not named:
            return False, f"Luganda card never names the recommended crop ({crop_lg} is missing)"

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
    echo = _prompt_echo(back)
    if echo:
        return False, f"back-translation echoes the instructions or the tool: {echo}"
    for word in ("national", "country", "countrywide", "regional", "nationwide"):
        if word in back:
            return False, f"back-translation widens the scale beyond district: {word}"

    crops = _crop_words(result)
    for crop in FOREIGN_CROPS:
        if crop in back and crop not in crops:
            return False, f"back-translation names a crop that is not in the facts: {crop}"

    # A favourable reason read as unusable is a reversed direction. The phrase
    # list is a wide net; the sentence check that follows reads the direction
    # sentence itself, so "not suitable" in it rejects whatever wraps it.
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

    flip = _polarity_fault(back, result)
    if flip:
        return False, f"back-translation reads the pair direction the wrong way: {flip}"

    # An allowed crop named more often than the card names it is a crop the
    # facts never held. One extra mention is allowed, because a faithful
    # rendering may name a crop once where the English card used a pronoun.
    # More than one extra means an invented crop word came back as an allowed
    # crop, such as a made-up name that renders as "beans".
    src_counts = _crop_counts(card_en, result)
    for name, count in _crop_counts(back, result).items():
        if count > src_counts.get(name, 0) + 1:
            return False, f"back-translation names {name} {count} times against {src_counts.get(name, 0)} in the card"

    # A tie the facts do not hold must not appear in the round trip either.
    # The other side is held on the English card, because a tie reads back in
    # many forms, such as "the order decided", and this check reads one word.
    if not facts.get("tie_line") and re.search(r"\btie", back):
        return False, "back-translation claims a tie that the facts do not hold"

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


def luganda_crop_name(crop: str) -> tuple[str | None, bool]:
    """The Luganda name of a crop, and whether the lookup could be judged.

    The name is read from the translator the card already uses, then read
    back. A name of one word or several is confirmed the same way: every word
    of the crop name must return, plurals allowed. A name that reads back as
    a different plant is not a name to judge a card by. The second value says
    whether the lookup was judged at all. A reachable translator that yields
    no confirmed name fails closed: an invented crop word could hide in that
    window, so the card that depends on it is unverifiable. No token means no
    lookup was possible, and the card is judged without the name check.
    """
    if not os.environ.get("SUNBIRD_API_TOKEN", "").strip():
        return None, False
    lg, _ = sunbird_translate(crop, "eng", "lug")
    if not lg:
        return None, True
    word = lg.strip().strip(".").strip()
    if not word or word.lower() in crop.lower():
        # The translator gave the English name back, so it holds nothing to
        # check a Luganda card against.
        return None, True
    back, _ = sunbird_translate(word, "lug", "eng")
    confirmed = back and all(
        re.search(r"\b" + re.escape(part) + r"s?\b", back.lower())
        for part in crop.lower().split()
    )
    if not confirmed:
        return None, True
    return word.lower(), True


def _translated_card(card_en: str, result: dict, notes: list[str]) -> str | None:
    """Translate card_en, read it back, and check the reading, with one retry.

    The translator rephrases between calls, so one failed reading does not
    prove the card is bad. A second reading is taken. A card that fails both
    readings is left out rather than sent unverified.
    """
    for attempt in (1, 2):
        translated, note = sunbird_translate(card_en)
        notes.append(note if attempt == 1 else f"second attempt: {note}")
        if translated is None:
            return None
        back, note = sunbird_translate(translated, source="lug", target="eng")
        notes.append(f"round trip back: {note}")
        if back is None:
            notes.append("Luganda card dropped: it could not be read back, so it is unverified.")
            return None
        ok, reason = check_luganda(translated, card_en, back, result)
        if ok:
            notes.append("Luganda card passed the month and round-trip check.")
            return translated
        notes.append(f"Luganda card dropped on reading {attempt}: {reason}.")
    return None


def build_cards(result: dict) -> tuple[str, str | None, list[str]]:
    """Return (card_en, card_lg_or_none, notes). Notes say what each step did."""
    notes: list[str] = []
    card, note = groq_card(result)
    notes.append(note)
    if card is not None:
        ok, reason = check_card(card, result)
        if not ok:
            notes.append(f"Draft rejected ({reason}), plain card used.")
            card = None
    if card is None:
        card = template_card(result)

    # The English card is final at this point. The Luganda card is a copy of it
    # and must prove it says the same thing before it is sent.
    card_lg = _translated_card(card, result, notes)
    if card_lg is None and card != template_card(result):
        # The model card could not be verified in Luganda. The plain card is
        # used for both texts, so the Luganda area never disagrees with the
        # English card.
        notes.append("The model card fell back to the plain card, so both texts agree.")
        card = template_card(result)
        card_lg = _translated_card(card, result, notes)
    return card, card_lg, notes
