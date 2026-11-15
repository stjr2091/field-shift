# Recommendation service

HTTP routes that answer a crop question from the files the notebook writes.
They compute nothing from the weather themselves and hold no crop numbers of
their own.

    python server/app.py            # http://127.0.0.1:8099
    PORT=9000 python server/app.py

Run `python server/test_recommend.py` for the checks. They use no network and
no credentials.

## Routes

- `POST /recommend` answers one request.
- `GET /assumption` returns `{"season_assumption": "..."}`, the same sentence
  the POST response carries. It reads the data file only, with no model call,
  so the page can show the assumption before any advice is given.
- `GET /health` returns a fixed word.

## Request

`POST /recommend`

```json
{
  "previous_crops": ["sorghum"],
  "soil_ph": 6.1,
  "moisture": "dry",
  "district": "Soroti",
  "planting_date": "2026-08-20"
}
```

| Field | Required | Notes |
| --- | --- | --- |
| `previous_crops` | yes | Crop keys, newest last. Send `[]` for no history. A blank entry is dropped. A crop outside the five is refused. |
| `soil_ph` | no | Number, 0 to 14. Compared with the sourced pH range of each crop. |
| `moisture` | no | Free text, reported in the reasons. The table holds no moisture threshold, so it never ranks a crop. |
| `district` | no | `"auto"` or a blank entry uses the one site the data file holds. A different name is refused rather than answered with another district's numbers. |
| `planting_date` | no | ISO date, `YYYY-MM-DD`. It picks the season whose window the date falls in, or the next one to come. Absent or blank means today's date (Africa/Kampala) makes that pick. A date that is not a real calendar day is refused. |

Crop keys: `maize`, `common_bean`, `finger_millet`, `sorghum`, `groundnut`.

## Response

```json
{
  "recommended_crop": "Maize",
  "when": "15 March to 15 August",
  "why": "No rotation rule is held for Maize after Sorghum; the pair is unknown.",
  "alternative": "Common bean",
  "reasons": ["..."],
  "season_assumption": "No planting date was entered, so today's date (15 November 2026) picks the second rains season (August to November); ...",
  "card_en": "...",
  "card_lg": "..."
}
```

`card_lg` is absent when no verified translation was made. `season_assumption`
is always present: it names the season the windows assume, the date that made
the pick, and the data fact that governs it. `reasons` carries the evidence
for the answer, one sentence each, in the order it was used.

## How the season is picked

The data file holds a window for each season from the same NASA POWER onset
analysis the reasons report. A request with a `planting_date` uses the season
whose window the date falls in; a date between windows, or after both, uses
the season whose window opens next, which after the second rains is the next
year's first rains. A request with no date lets today's date, read in
Africa/Kampala, make the same pick, and the response says so in
`season_assumption`. The windows shown are the chosen season's: a crop with
no sourced window for that season is told so, and is never shown another
season's window instead. The crop ranking, the rotation guards and the card
checks run the same way for either season.

`422` means the request cannot be answered honestly, and `error` says why.
`400` means the body is not JSON. `404` means the route is not one of the three.

## Where each answer comes from

| Step | Source | What it may not do |
| --- | --- | --- |
| Crop list, windows, pH ranges | `results/app_data.json`, built from `rules/rules.csv` | Add a crop or a number that the table does not hold |
| Rotation pairing | `notebooks/crop_path.py` | Treat a pair with no row as evidence |
| Card text | the result fields only | Add a figure, a date, a month, a claim or a confidence word |
| Luganda | Sunbird, from the English card | Change the meaning or add content |

A translated card is checked before it is sent. The window months must survive
translation, and the card is translated back to English and read again. A crop
that appeared, a claim, a wider scope, a reversed direction, or an allowed crop
named more often than the card names it drops the Luganda card. The Luganda
card must also name the recommended crop, in the Luganda name the translator
holds, one word or several, or in the English name, so an invented crop word
cannot hide behind a faithful reading. That name comes from a live lookup, and
the guard fails closed on it: a name counts only when it reads back as the
crop it stands for, and when the translator is reachable but no name can be
confirmed, the card is unverifiable in exactly the window where an invented
crop word hides, so the Luganda card is dropped. A failed reading is retried once,
because the translator rephrases between calls. An unverified translation is
never sent: the English card already carries the answer, and the notes say why
the Luganda one was dropped. When a model card cannot be verified in Luganda,
both texts fall back to the plain card, so the Luganda area never disagrees
with the English card.

The plain card is the primary card. It speaks to the farmer, holds one idea per
sentence, and always states the crop and window, the reason, the alternative,
the season assumption and the district scale. The card step calls a hosted
model only to phrase the supplied fields on top of that, and every draft is
checked against those fields before it is used. A draft is rejected when it
adds a number, a crop or a claim that is not in the fields, widens the scale
past the district, abbreviates a month, omits the alternative, omits the season
assumption, echoes the instructions, speaks about the tool instead of to the
farmer, reverses the direction of the reason, or drops a month of the published
window. A rejected draft is never repaired: the plain card is used.

The ranking never offers the crop that was grown last, neither as the
recommendation nor as the alternative. The reasons state that guard in plain
words, and the facts carry it so the cards can too.

When the rules leave two or more crops level, the order of the crop list decided
which one is named. Both cards say so, and a card that leaves the tie out is
rejected. A card that claims a tie the facts do not hold is rejected as well.
See `server/card.py`.

## Credentials

| Variable | Service | Without it |
| --- | --- | --- |
| `GROQ_API_KEY` | Card phrasing | The plain card is used. The service still answers. |
| `SUNBIRD_API_TOKEN` | Luganda translation | `card_lg` is left out. |

No key value belongs in this repository. Set the variables in the environment
that runs the service.

## Limits that travel with every answer

- One NASA POWER cell covers about 55 by 70 km. District-scale, not parcel-scale.
- This is not a yield prediction. No yield, harvest or income figure is held.
- Rotation reasons are a direction only, except the finger millet after sorghum
  pair, which rests on farmer survey knowledge. Neither is a measured effect.
- No crop has a published planting rainfall threshold, so a sowing date is never
  given. A window is a range, not a date.
- Three crops pass the sourced-rule cut and can be recommended: maize, common
  bean and finger millet. Sorghum and groundnut have no sourced rows, so they are
  accepted as a previous crop but never recommended. A crop with no rows is not
  ranked, and no value is invented to let it appear.
- Finger millet soil type is not held. Its planting window is borrowed from the
  maize row, and the data file carries that limitation.
