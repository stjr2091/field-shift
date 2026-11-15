# 🌱 AgriCloud · Web Interface

**A simple form for crop options, seasonal evidence and clear next checks.**

AgriCloud is built for the **NASA Space Apps Challenge — Field Shift category**. For the complete project setup, reproducible Python notebooks, Google Colab instructions, dependencies and AI-use information, see the [project README](../README.md).

[Run the app](../README.md#-quick-start) · [Reproduce the data](../README.md#-reproduce-the-analysis) · [API reference](../server/README.md) · [Sources](../SOURCES.md)

## Run it

From the repository root:

```bash
python -m http.server 8000 --bind 127.0.0.1
```

Open the [sample interface](http://127.0.0.1:8000/app/index.html?api=mock). No frontend build or package installation is required.

To use the recommendation service, start it in another terminal:

```bash
python server/app.py
```

Then open [AgriCloud with the local backend](http://127.0.0.1:8000/app/index.html?api=http://127.0.0.1:8099/recommend).

The voice questions use the same local service. Install the optional
dependencies in a DeepSpeech-compatible Python environment, then choose
**Start voice questions** to answer the prompts using the microphone. Review
the transcribed crop history, pH and moisture before submitting; the result
card has a **Listen to this advice** control. Voice input/output is English.
See the [voice routes and setup](../server/README.md#optional-voice-routes).

## Backend

The form sends crop history, optional soil pH, moisture, planting date and district to `POST /recommend`. The service validates the inputs and returns advice and supporting evidence. `GET /assumption` provides the season assumption.

The `api` query parameter selects the recommendation URL. Without it, or with `?api=mock`, the interface uses fixed samples. Samples do not recalculate advice for every input. A configured service error must not silently become a sample result.

See the [service documentation](../server/README.md) for request fields, credentials and optional integrations. Provider secrets belong only in the backend environment.

## Interface files

| File | Purpose |
| --- | --- |
| [index.html](index.html) | Form and result sections. |
| [app.js](app.js) | Input handling, submission and rendering. |
| [styles.css](styles.css) | Layout and presentation. |
| [app_data.json](app_data.json) | Fallback derived app data. |

## Limits

The interface presents supplied evidence; it does not invent agricultural advice. Seasonal suitability is separate from planting readiness, and forecast rainfall is not proof that a field is ready to plant.

Translation depends on provider availability, configured safeguards and meaning checks. Synthetic language fixtures are test strings, not Luganda. The app does not predict yield or income.

[Method](../docs/method.md) · [AI use](../AI_USE.md) · [License](../LICENSE)
