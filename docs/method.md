# Method — Field Shift analysis decisions

Site: 1.35 N, 32.45 E (Nakasongola), NASA POWER daily 1991–2025, SoilGrids point extract. One decision per line; rejected alternative after the em dash; source or **assumption** at the end.

## D1. Onset definition

- **Rule.** Onset = the first day in a season search window where the trailing 10-day rainfall sum is ≥ 20 mm AND the previous 10-day sum was < 20 mm (a crossing) AND root-zone wetness that day is ≥ 0.40. Crop rainfall thresholds come from `rules/rules.csv` when those rows land; 20 mm/10 d is the site screening value until then — **assumption**, not a sourced agronomic law. — Rejected: the widely used Stern/Dodoma criteria (e.g. 20 mm in 2 days plus no 10-day dry spell in the next 30) — stricter and better sourced, but heavier and not what the notebook computes; pick one, do not mix.
- **Season search windows.** First rains 1 Feb – 31 May, second rains 1 Aug – 30 Nov, per year — **assumption** bounding where we look; 7 of 35 first-rains years and 24 of 35 second-rains years are already above the threshold when the window opens, so a mid-window "onset" is often a re-crossing, not the season start.
- **What this supports.** The onset date of the *rainy season within a named search window* at district scale. It does not support a claim that planting on the onset day is optimal, or that the window bounds capture the true season start.

## D2. Comparing current practice vs the rainfall-supported window

- **Same footing.** Both the documented current-practice window and the rainfall-supported window are stated as calendar date ranges on the same site point, and compared on two axes: (a) coverage — the share of years (1991–2025) in which the current-practice window contains or precedes the computed onset; (b) median days between the current-practice start and the computed onset. Both windows use the same onset definition and the same years; no other adjustment — **assumption** for the comparison convention; the current-practice dates come from the Rakai/Nakasongola 2022 trial and MAAIF manuals in `rules/rules.csv`.
- **What this supports.** A district-scale statement like "the documented window opens N days before/after the median computed onset, and covers it in X/35 years". It does not support per-farm advice.

## D3. Zero and missing rainfall days

- **Zero rain is real.** A day with `PRECTOTCORR` = 0.0 is a genuine dry day and stays in every sum — zeros suppress the 10-day sum and can delay an onset; treating them as missing would bias onset earlier. — Rejected: dropping zero days — that inflates the rolling sum over wet days only and shifts onset earlier.
- **Missing is never a number.** POWER's −999 sentinel becomes NaN before any sum; a rolling 10-day sum over a window containing a NaN is NaN, so that day is skipped as an onset candidate, never counted as dry. This pull has zero sentinels and zero missing days (12,784 of 12,784 present), so the rule is dormant today but must stay in place — source: `scripts/download_data.py` and `notebooks/field_shift_data.py::read_power_csv`.
- **Months and years.** Monthly climatology and annual totals use only complete months/years (every day present, no missing rain) — source: `notebooks/field_shift_data.py::monthly_total_series`.

## D4. Does the ~50 km POWER cell support the Nakasongola claim?

- **Yes at district scale, no below it.** One POWER cell is ~0.5° × 0.625° (roughly 50–55 km), larger than Nakasongola district (~35 km across), so one cell spans the district and beyond — a district-level onset and window statement is defensible; a parish-, farm- or parcel-level claim is not. — Rejected: calling it "parcel-scale" — contradicted by the MERRA-2 grid. Source: `SOURCES.md` and POWER documentation (MERRA-2 native grid).
- **Consequences.** All results carry the district-scale caveat; no interpolation between cells (we have one point, not a grid); and the demo must not show parcel boundaries next to these numbers without the caveat on the same screen.

## D5. What SoilGrids pH and texture at 0–30 cm can and cannot support

- **Can.** A threshold *check against a mapping* of the site: e.g. pH(H₂O) 6.12, clay 38.6 %, sand 39.6 %, silt 21.8 % (depth-weighted 0–30 cm) screened against crop requirements like "maize tolerates pH 5.5–7.5" — a pass/fail flag at district-to-site scale. Source: `data/processed/soilgrids_site.json`; conversion per ISRIC (texture g/kg ÷ 10, pH × 10 ÷ 10).
- **Cannot.** (a) Fertiliser or amendment rates — pH 6.12 mapped ≠ a measured field pH; liming rates need a measurement. (b) Drainage, water-holding or compaction claims from texture alone at one point. (c) Any spatial gradient claim — one 250 m pixel is one number, no within-district variation. (d) Claims that ignore uncertainty: SoilGrids reports quantiles (Q0.5 median alongside the mean); where mean and median differ materially, the threshold check is not robust and should say so.
- **Depth.** 0–30 cm is the root-zone screening depth we chose — **assumption**; it matches the deepest SoilGrids layer pulled (15–30 cm), not a crop-specific rooting claim.

## D6. Independent cross-check (this branch, 14 Nov 2026)

- I re-implemented onset from the raw POWER CSV, written from scratch (`scripts/qa_onset_check.py`, this branch), same point, same years, same windows.
- **Result: 34 of 35 first-rains and all 35 second-rains dates match the notebook exactly** (median DOY 53 / 219; p25–p75 41–74 / 214–232 — all reproduced).
- **1 mismatch found and explained:** 2021 second rains, notebook says 6 Sep, exact arithmetic says 5 Sep. The 10-day sum ending 5 Sep 2021 is exactly 20.00 mm; in binary floating point it is 19.99999999999998, so `>= 20` fails by ~2e-14. Fix: sum in `Decimal`, or compare with a tolerance (`>= threshold - 1e-6`). Severity: cosmetic; it moves one date by one day in one year of 70.
- **Consequence of D1's crossing rule worth stating in the write-up:** in 24 of 35 second-rains years the reported "onset" is a re-crossing mid-season (the season was already wet on 1 Aug), so second-rains onset dates are "re-wetting dates", not season starts. The most affected years: 1991 (29 Sep vs 10 Jan unconstrained), 2012 (27 Oct vs 5 Mar). The notebook's own assumptions block says the windows "bound where we look"; docs should not present these as first rains of the season.
