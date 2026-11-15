# App

One small form and one advice card. No build step. No dependencies.

## Run it

Serve the repository root, then open `/app/index.html`:

    python3 -m http.server 8000

    http://localhost:8000/app/index.html

The district line reads the site name from `results/app_data.json`. A copy in
this folder is used as a fallback.

## Language

A single toggle at the top of the page switches the whole page between
English and Luganda: headings, form labels and hints, submit, footer, and
the result card. It re-renders in place and does not reload.

The Luganda strings live in `translations_lg.js`, one dict of key to Luganda.
Every string there comes from the Sunbird translation pass with a read-back
check. A key without an entry keeps its English text; nothing is invented.
The Luganda card itself comes from the service response (`card_lg`), which is
checked separately. In Luganda mode the card shows `card_lg` when the
response has one, and otherwise keeps the English card text with the
fallback line 'Luganda card unavailable for this advice' in Luganda.

## Backend

The form posts JSON to the advice service:

    POST {previous_crops: string[], soil_ph?: number, moisture?: string, district?: string}

The response shape the card expects:

    {recommended_crop: string, when: string, why: string, alternative: string,
     reasons: string[], card_en: string, card_lg?: string, season_assumption: string}

`season_assumption` is one plain sentence naming the season the advice assumes.
The card shows it on the result and next to the submit button before the advice
is requested. When `card_lg` is missing, the Luganda area says so in one line
instead of staying blank.

`previous_crops` carries crop keys, oldest first, newest last:
`maize`, `common_bean`, `finger_millet`, `sorghum`, `groundnut`, `other`.

### Point it at the live service

By default the page uses `mock_response.json`, a local sample, so the card can
be tested before the service exists. Add the flag to use the real address:

    http://localhost:8000/app/index.html?api=https://example.org/advice

Two samples cover the Luganda paths: the default shows the Luganda card, and

    http://localhost:8000/app/index.html?api=mock-nolg

shows the missing-card note instead.

The service must allow the browser's origin (CORS) and answer with the JSON
shape above. No other setting is needed.

On page load the form also asks `GET <api-base>/assumption` for the season
assumption, where the base is the `?api=` URL without a trailing
`/recommend`. It returns `{season_assumption: string}` and fills the note by
the submit button before any advice is requested. If that fetch fails, the
note stays empty until the first advice.

## Limits

- The district is automatic and fixed to the site in `results/app_data.json`.
  There is no picker. A location lookup is still a decision, not built here.
- Optional values left blank are left out of the request. They never block the
  form.
- The card only repeats what the service returns. It adds no advice.
