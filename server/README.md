# Recommendation service

One HTTP route that answers a crop question from the files the notebook writes.
It computes nothing from the weather itself and holds no crop numbers of its own.

    python server/app.py            # http://127.0.0.1:8099
    PORT=9000 python server/app.py

Run `python server/test_recommend.py` for the checks. They use no network and
no credentials.

## Request

`POST /recommend`

```json
{
  "previous_crops": ["sorghum"],
  "soil_ph": 6.1,
  "moisture": "dry",
  "district": "Soroti"
}
```

| Field | Required | Notes |
| --- | --- | --- |
| `previous_crops` | yes | Crop keys, newest last. Send `[]` for no history. A blank entry is dropped. A crop outside the five is refused. |
| `soil_ph` | no | Number, 0 to 14. Compared with the sourced pH range of each crop. |
| `moisture` | no | Free text, reported in the reasons. The table holds no moisture threshold, so it never ranks a crop. |
| `district` | no | `"auto"` or a blank entry uses the one site the data file holds. A different name is refused rather than answered with another district's numbers. |

Crop keys: `maize`, `common_bean`, `finger_millet`, `sorghum`, `groundnut`.

## Response

```json
{
  "recommended_crop": "Maize",
  "when": "15 March to 15 August",
  "why": "No rotation rule is held for Maize after Sorghum. The pair is unknown.",
  "alternative": "Common bean",
  "reasons": ["..."],
  "card_en": "...",
  "card_lg": "..."
}
```

`card_lg` is absent when no translation was made. `reasons` carries the evidence
for the answer, one sentence each, in the order it was used.

`422` means the request cannot be answered honestly, and `error` says why.
`400` means the body is not JSON. `404` means the route is not `/recommend`.

## Where each answer comes from

| Step | Source | What it may not do |
| --- | --- | --- |
| Crop list, windows, pH ranges | `results/app_data.json`, built from `rules/rules.csv` | Add a crop or a number that the table does not hold |
| Rotation pairing | `notebooks/crop_path.py` | Treat a pair with no row as evidence |
| Card text | the result fields only | Add a figure, a date, a month, a claim or a confidence word |
| Luganda | Sunbird, from the English card | Change the meaning or add content |

The card step calls a hosted model to phrase the supplied fields. Every draft is
checked against those fields before it is used. A draft that holds a number or a
month not in the fields, or a claim about yield, success or confidence, is
rejected and the plain card is used instead. See `server/card.py`.

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
