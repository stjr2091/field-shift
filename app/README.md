# App

One small form and one advice card. No build step. No dependencies.

## Run it

Serve the repository root, then open `/app/index.html`:

    python3 -m http.server 8000

    http://localhost:8000/app/index.html

The district line reads the site name from `results/app_data.json`. A copy in
this folder is used as a fallback.

## Backend

The form posts JSON to the advice service:

    POST {previous_crops: string[], soil_ph?: number, moisture?: string,
          planting_date?: string, district?: string}

`planting_date` is ISO YYYY-MM-DD from the optional date input. When it is
blank the field is left out and the server picks the season from today's
date. Any check on the date itself is the server's business.

The response shape the card expects:

    {recommended_crop: string, when: string, why: string, alternative: string,
     reasons: string[], card_en: string, card_lg?: string, season_assumption: string,
     error?: string}

`season_assumption` is one plain sentence naming the season the advice assumes.
The card shows it on the result and next to the submit button before the advice
is requested. When `card_lg` is missing, the Luganda area says so in one line
instead of staying blank. If the response carries an `error` string, the form
shows it in the error line instead of the card.

`previous_crops` carries crop keys, oldest first, newest last:
`maize`, `common_bean`, `finger_millet`, `sorghum`, `groundnut`, `other`.

### Point it at the live service

By default the page uses `mock_response.json`, a local sample, so the card can
be tested before the service exists. Add the flag to use the real address:

    http://localhost:8000/app/index.html?api=https://example.org/advice

The samples follow the request: a blank planting date shows the default
second-season sample without a Luganda card, and a chosen date shows the
dated first-rains sample with the Luganda card. The flag

    http://localhost:8000/app/index.html?api=mock-nolg

removes the Luganda card from either sample, so the missing-card note shows.

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
