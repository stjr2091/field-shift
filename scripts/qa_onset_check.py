"""Independent onset cross-check for Field Shift.

Re-implements onset detection from scratch against the raw NASA POWER CSV and
compares every date with the notebook's committed results/site_climate.json.

Same rule as the notebook (docs/method.md D1): first day in the season window
where the trailing 10-day rain sum is >= 20 mm, the previous 10-day sum was
< 20 mm, and GWETROOT >= 0.40. Written with Decimal so the 20.00 mm boundary is
exact; run it to reproduce the comparison in D6.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POWER = ROOT / "data" / "raw" / "power_daily_1.35N_32.45E_1991-2025.csv"
NOTEBOOK_JSON = ROOT / "results" / "site_climate.json"

RAIN_10D_MM = Decimal("20")
GWETROOT_MIN = 0.40
SEASONS = {"first_rains": ((2, 1), (5, 31)), "second_rains": ((8, 1), (11, 30))}
YEARS = range(1991, 2026)


def load_daily() -> dict[date, tuple[Decimal, float]]:
    text = POWER.read_text(encoding="utf-8")
    table = text.split("-END HEADER-", 1)[1].strip()
    out: dict[date, tuple[Decimal, float]] = {}
    for row in csv.DictReader(io.StringIO(table)):
        d = date(int(row["YEAR"]), 1, 1) + timedelta(days=int(row["DOY"]) - 1)
        out[d] = (Decimal(row["PRECTOTCORR"]), float(row["GWETROOT"]))
    return out


def roll10(rain: dict[date, Decimal], day: date) -> Decimal | None:
    vals = [rain.get(day - timedelta(days=k)) for k in range(10)]
    if any(v is None for v in vals):
        return None
    return sum(vals)


def detect_onset(daily, year: int, window) -> date | None:
    rain = {d: v[0] for d, v in daily.items()}
    d, end = date(year, *window[0]), date(year, *window[1])
    while d <= end:
        s = roll10(rain, d)
        if s is not None:
            prev = roll10(rain, d - timedelta(days=10))
            if s >= RAIN_10D_MM and daily[d][1] >= GWETROOT_MIN and (prev is None or prev < RAIN_10D_MM):
                return d
        d += timedelta(days=1)
    return None


def main() -> int:
    daily = load_daily()
    nb = json.loads(NOTEBOOK_JSON.read_text(encoding="utf-8"))
    mismatches = []
    for season, window in SEASONS.items():
        for year in YEARS:
            mine = detect_onset(daily, year, window)
            row = next(
                r for r in nb["onset_by_year"] if r["season"] == season and r["year"] == year
            )
            theirs = date.fromisoformat(row["onset_date"]) if row["onset_found"] else None
            if mine != theirs:
                mismatches.append((season, year, theirs, mine))
    print(f"years checked: {2 * len(list(YEARS))}, mismatches: {len(mismatches)}")
    for season, year, theirs, mine in mismatches:
        print(f"  {season} {year}: notebook {theirs} vs independent {mine}")
    return len(mismatches)


if __name__ == "__main__":
    raise SystemExit(0 if main() == 0 else 1)
