# Late Rains, Next Crop

A decision aid for Soroti district, Uganda. One question: what do I plant, and when?

## What this is

This is a one-page web app and the analysis behind it. It reads a rainfall record and a
soil estimate for one point in Soroti district, then shows:

- when the rains start, and how much that date varies,
- how often a false start follows planting,
- which crops the sourced evidence supports,
- and what the app cannot tell you.

The app shows no yield figure. It does not predict a harvest. It shows the date the
rain record supports and lists the crops the sourced evidence covers, and it states
where the two are not joined: no crop has a sourced planting rainfall threshold, so
no crop's window is compared with the rain record.

## The site

Soroti district, one point: 1.79 N, 33.50 E.

One NASA POWER grid cell covers about 55 by 70 km. That is about the size of the district.
The statements here are district-scale. They are not farm-scale and not parcel-scale.

## The rain record

Source: NASA POWER daily data, MERRA-2, 1 January 1991 to 31 December 2025.

- 35 complete years.
- 12,784 of 12,784 days present. No missing day, no duplicate date, no sentinel value.
- Mean yearly rain: 843.0 mm. Median: 839.4 mm.
- Lowest year: 554.0 mm. Highest: 1,395.6 mm.

The record varies by more than two and a half times between the driest and wettest year.
That spread is why a single figure is not advice.

## When the rains start

A method is applied to the record, not assumed. The rule looks for a 10-day period in the
season window where rain reaches 20 mm and the root-zone wetness is above 0.40.

First rains, window 1 February to 31 May:

- An onset is found in 35 of 35 years.
- Median date: day 77 of the year, which is 18 March. The spread is wide: the middle half of
  years start between day 56 and day 90, and the earliest and latest are day 32 and day 129.

That spread is the main finding. A single planting date for the district cannot be right
in most years.

Second rains, window 1 August to 30 November:

- An onset is found in 34 of 35 years. In 2007 no 10-day period reaches 20 mm, so the rule
  finds no onset. That year is reported as having no onset, not as a missing value.
- Median: day 225 of the year, which is 13 August. Middle half: day 214 to day 243.

These second-rains dates are re-wetting dates, not the start of a separate dry-to-wet
season. The window opens on 1 August, when the ground is often already wet. The app must not
call them season starts, and neither does this note.

## False starts and dry spells

A dry spell is 7 or more days below 1 mm of rain. The app counts dry spells in the 30 days
starting on the onset date, and the onset day counts as day 1.

- First rains: a 7-day spell in 21 of 35 years. 23 spells in total. Longest: 25 days.
- Second rains: a spell in 8 of 34 years. 9 spells. Longest: 16 days.

The onset date is a risk marker, not a green light. In three years out of five, a first-rains
start is followed by a dry week.

The analysis note carries a second, narrower test: 7 dry days inside the 21 days after onset.
That test gives 8 of 35 years in the first rains. The two windows start on different dates
and answer different questions, so the figures 21 and 8 must never be shown as disagreeing.

## The soil, and what it is not

Source: ISRIC SoilGrids v2.0, a point query at the same coordinates.

Depth-weighted 0-30 cm: pH 6.12, clay 40.73 per cent, sand 38.87 per cent, silt 20.32 per
cent. The three textures sum to 99.92 per cent.

These are model estimates, not measurements. SoilGrids predicts each value from a global
model and the observations behind it. No soil sample was taken at Soroti and none is held.
Text here says "model estimate" for that reason.

The soil class is not confident. The most likely class is Cambisols, at 17 per cent
probability. The next four are Vertisols 10, Gleysols 9, Arenosols 8 and Fluvisols 7. The top
five account for 51 per cent, so the cell sits in a mixed-soil area.

pH 6.12 falls inside the optimum range for both maize and beans. That is a useful check and
nothing more: one model estimate at one point cannot set a lime rate.

## The crops

The crop table is Stephen's released table, with its tags kept as released.

Three crops appear, each with three of four parameters sourced:

| Crop | Crop duration | Soil pH | Temperature | Planting rainfall threshold |
|---|---|---|---|---|
| Maize | 110-120 days, MAAIF manual, Soroti named in the row | 5.5-7.0, MAAIF | 30-34 optimum, limits 10 and 40 | unknown |
| Common bean | 58-120 days, MAAIF | 5.8-6.5, acid limit 5.2 | 20-28 optimum, limits 15 and 32 | unknown |
| Finger millet | 75-180 days, EcoCrop | 6-7 optimum, 5.5-8.2 absolute, EcoCrop | 18-30 optimum, limits 8 and 35, EcoCrop | unknown |

Sorghum and groundnut do not appear. No manual for either is held, so no row is sourced for
them and the cut rule removes them.

**The honest gap, stated once and plainly.** No crop in this table has a planting rainfall
threshold. There is no sourced millimetre figure that says "sow at this point". Both manuals
say only "Planting should be done on the onset of rains" and give no number. So the app
answers the crop part of the question and the rain part separately. It does not join them
with a number it does not have.

The finger millet planting window is borrowed from the maize row. Both are rain-fed cereals
planted in the same rains, and no millet calendar for Teso was opened. This is the largest
assumption in the table and the app says so.

## The wetness gate does real work here

The rule requires root-zone wetness above 0.40. At this site it sits below that on 4,732 of
12,784 days. It changes the first-rains onset in 11 of 35 years: by one day in nine of them,
by 22 days in 1996 and 25 days in 2003. It never changes a second-rains date.

This matters for honesty: the gate is not decoration, and a rule stated without it would give
different dates.

## What was checked, and by whom

The numbers in this note were recomputed from the raw files by a checker who did not write
the pipeline. The checker's script is in the shared evidence folder and does not import the
pipeline code.

- 128 rows compared. 125 match. 3 differ by 0.1, all from half-values rounding down.
- Every one of 69 season-year onset dates matches.
- Both raw files match the live services byte for byte on the day checked.

The check record is `qa/app_rebuild/check_soroti_app_numbers.md`.

## What this does not do

- No yield prediction. No harvest estimate.
- No farm-scale or parcel-scale claim. One grid cell is about the district.
- No gauge comparison. No gauge series is held by this team and none has been pulled, so the
  comparison the papers describe is not done. This does not mean no gauge record exists for
  the region.
- No computed season length. Cessation is not implemented, so a crop's published duration is
  never compared with a season we measured. Where the app compares a duration with the next
  rains, it uses the shortest published duration, and it states the longest beside it. For
  finger millet the two ends disagree: 75 days ends 1 June and fits, 180 days ends
  14 September and overlaps the second rains. The page says so rather than showing one end.
- No per-crop window comparison. The rainfall-supported window and the gap in days are not
  computed, so no such table is shown. It is not filled in with a rule that does not exist.
- No field measurement of soil. The pH and texture are model estimates.
- No causal claim that an onset date leads to a good crop. The link is not tested.

## Known limitations, carried forward

- The rounding detail above is recorded, not fixed, because a re-run costs a full re-check for
  0.1.
- The season boundaries are an administrative choice from the MAAIF calendar, not a result
  derived from the data.
- The second season's dates are re-wetting dates, not season starts.
- The dry-spell windows in this note and in the analysis differ, 30 days against 21, and are
  never compared.
- A second rainfall record (CHIRPS) was pulled during the analysis and is held outside the
  repository. It is not shown in the app and no record is chosen as primary. The two disagree.
- Rotation is recorded as a direction only, with no number. The app shows all three tagged
  rows when a previous crop is chosen: the finger millet row as farmer survey, not a trial,
  and the two crop-pair rows as assumed, with no source. Each row is labelled untested, and
  the panel states that no nitrogen, yield, plot or trial data is held, so no rotation
  effect can be measured. No rotation reason is advice.

## Sources

- NASA POWER daily point data, MERRA-2, for 1.79 N, 33.50 E, 1991-2025.
- ISRIC SoilGrids v2.0, point query, properties and WRB classification.
- MAAIF maize training manual for extension workers, 2023.
- MAAIF beans training manual for extension workers, 2023.
- FAO EcoCrop datasheets for maize, common bean and finger millet.
- National Research Council, Lost Crops of Africa, Volume I, chapter 2, Finger Millet, 1996.

## Status of this draft

This is a draft for review. Figures are from the committed results and the check record.
The crop section follows the corrected table, which is merged. The millet rainfall row is
settled: it stays as reference evidence with its tag unchanged, it is not a Soroti sowing
trigger, and no parameter is reclassified.
