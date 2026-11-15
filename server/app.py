"""A small HTTP service in front of the crop recommendation.

    python server/app.py            # http://127.0.0.1:8099
    PORT=9000 python server/app.py

One route: POST /recommend. GET /health returns a fixed word.

The response carries the agreed fields only. Any extra field the calculation
needs is removed before the reply is sent, so the frontend contract cannot
drift without a deliberate change here.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "notebooks"))

import card  # noqa: E402
import recommend as calc  # noqa: E402

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8099"))

# The response fields agreed with the page. Nothing else is sent.
FIELDS = [
    "recommended_crop",
    "when",
    "why",
    "alternative",
    "reasons",
    "card_en",
    "card_lg",
]

# The request fields. district is accepted and echoed only as a check, because
# the data file holds one site. A district other than that site is refused
# rather than answered with another district's numbers.
REQUEST_FIELDS = {"previous_crops", "soil_ph", "moisture", "district"}


def handle_request(payload: dict) -> dict:
    """Answer one request. Raises calc.RequestError for a bad request."""
    if not isinstance(payload, dict):
        raise calc.RequestError("The request body must be a JSON object.")

    unknown = set(payload) - REQUEST_FIELDS
    if unknown:
        raise calc.RequestError(f"Unknown request fields: {', '.join(sorted(unknown))}.")
    if "previous_crops" not in payload:
        raise calc.RequestError("previous_crops is required. Send [] for no history.")

    data = calc.load_data()
    site = (data.get("site") or {}).get("name", "")
    district = (payload.get("district") or "").strip()
    # "auto" and a blank mean the same thing: use the one site the data file
    # holds. Only a different named district is refused, because answering it
    # with these numbers would be a claim about a district we did not measure.
    if district.lower() not in ("", "auto") and site and district.lower() != site.lower():
        raise calc.RequestError(
            f"This service holds data for {site} only. The request named {district}."
        )

    result = calc.recommend(
        previous_crops=payload.get("previous_crops"),
        soil_ph=payload.get("soil_ph"),
        moisture=payload.get("moisture"),
        data=data,
    )
    card_en, card_lg, notes = card.build_cards(result)

    out = {key: result[key] for key in FIELDS if key in result}
    out["card_en"] = card_en
    if card_lg:
        out["card_lg"] = card_lg
    # Why each text step fell back. Kept out of the contract, printed only.
    return {"body": out, "notes": notes}


class Handler(BaseHTTPRequestHandler):
    server_version = "field-shift/1.0"

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, {})

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/health", ""):
            return self._send(200, {"status": "ok"})
        self._send(404, {"error": "Use POST /recommend."})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/recommend":
            return self._send(404, {"error": "Use POST /recommend."})

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return self._send(400, {"error": "The request body is empty."})
        if length > 10_000:
            return self._send(413, {"error": "The request body is too large."})

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._send(400, {"error": "The body is not valid JSON."})

        try:
            outcome = handle_request(payload)
        except calc.RequestError as error:
            return self._send(422, {"error": str(error)})

        for note in outcome["notes"]:
            print(f"note: {note}", file=sys.stderr)
        self._send(200, outcome["body"])

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", file=sys.stderr)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"listening on http://{HOST}:{PORT}  POST /recommend", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped", file=sys.stderr)


if __name__ == "__main__":
    main()
