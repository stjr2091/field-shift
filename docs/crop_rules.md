# Crop rules — what the table holds and what it cannot support

Thirty-five rule rows, one per rule, in `rules/rules.csv`. Each row carries a
tag: `sourced`, `assumed` or `unknown`. A row is `sourced` only when it has a
link, a page and the line quoted as printed.

The app counts four parameters per crop: season length, water, pH and
temperature. A crop appears only when at least three of the four have a sourced
row. That rule is fixed in `docs/plan.md` and this table does not change it.

## What appears, and why

| Crop | Sourced of four | Unknown | Appears |
| --- | --- | --- | --- |
| Maize | 3 | rainfall threshold | yes |
| Common bean | 3 | rainfall threshold | yes |
| Finger millet | 3 | rainfall threshold | yes |
| Sorghum | 0 | all four | no, not in the table |
| Groundnut | 0 | all four | no, not in the table |

Sorghum and groundnut are not in the released table, so they are not in this
file and they do not appear in the app. The app shows the cut on its rules
coverage table, with the count of sourced rows beside it.

The four parameters the cut counts are exactly the names in the code:
`planting_rainfall_threshold`, `season_length`, `ph_range` and `temp_range`.
Seasonal rainfall figures do not sit under `planting_rainfall_threshold`. They
are carried under `season_water_need_mm`, which is not one of the four, because
a seasonal total is not a sowing trigger. So the threshold stays unknown for
every crop, and each crop clears the cut on season length, pH and temperature.

Finger millet's water and planting-window rows are also reference evidence: the
millet chapter gives 500-1,000 mm for the crop, not a Soroti threshold, and the
planting window is borrowed from the maize row. Neither counts toward the cut.


## Two later sources, added beside the table

The workbook was drafted before two source corrections were found. Both are
added as their own rows. Neither replaces the row it corrects, because a reader
should see the earlier assumption and the later evidence together.

1. **Maize rainfall per season.** The workbook tags this assumed from EcoCrop.
   The maize manual gives a seasonal figure on PDF page 8: "Maize prefers
   rainfall of 500 to 600 mm as the optimal range and well distributed over the
   growing season." The assumed EcoCrop row stays visible beside it.
2. **Finger millet rainfall.** The millet chapter gives page 56: "It requires a
   moderate rainfall (500-1,000 mm), well distributed during the growing season
   with an absence of prolonged droughts." The caveat travels with the number:
   no prolonged drought, and dry weather at harvest. This is a seasonal water
   requirement, not a planting threshold, and it is not used as one.

   The quote is checked word for word, and it is carried as `assumed`, not
   `sourced`. It is the chapter's single millimetre figure for the crop, not a
   threshold for this site and not a release of the crop table. So it does not
   count toward the three of four.

## Temperature

The workbook has no temperature row for any crop. Two manuals and the EcoCrop
data sheet give one, and each is quoted as printed, including the `oC` form:

- Maize, PDF page 8: "It is well adapted in warm condition with optimum
  temperature for plant growth ranges of 30oC – 34oC. Temperatures below 10oC
  and above 40oC result in poor growth and death of the maize plant."
- Beans, PDF page 9: "Beans thrives best in a warm climate of optimum growing
  temperature range of 20 to 28oC with a minimum of 15oC and a maximum of 32oC.
  Temperatures above 32oC and below 15oC will cause poor pod set resulting in
  yield loss."

- Finger millet, page 57, section High Temperature: "Finger millet thrives under
  hot conditions. It can grow where temperatures are as high as 35°C. In Uganda,
  the crop grows best where the average maximum temperature exceeds 27°C and the
  average minimum does not fall below 18°C."

Each is one row. For maize and beans the optimum range is the value and the
outer limits sit in the note. Finger millet has two rows. EcoCrop gives its
optimum, 18-30, with 8 and 35 as the absolute limits in the note, and the app
reads that pair. The millet chapter row sits beside it as a cross-check and
carries no range, because 18 is the Uganda average-minimum floor and 35 is the
growth ceiling, which is not an optimum pair. The Uganda optimum line stays in
that row's quote rather than being converted into a range.

## pH

Maize keeps the workbook value from PDF page 25, 5.5-7.0. The same manual gives
5.0-7.0 on page 9; that variant is recorded in the note and the two are not
averaged. The generic "pH range 5.5 to 6.5 for most crops" lines on pages 21 and
24 are textbook lines, not a maize value, and are not used.

Beans uses 5.8-6.5 from PDF page 11, with the sensitivity below 5.2 in the same
quote.

Finger millet has no pH line anywhere in the millet chapter, so its pH comes from
EcoCrop alone: optimum 6-7, absolute 5.5-8.2. That row is sourced, because
EcoCrop states it for the crop, but it is not a Ugandan figure and the note says
so.

The beans temperature passage is on PDF page 9. An earlier note placed it on
page 11, which is the maturity page; page 9 is where the sentence sits.

## The five limitations, carried from the workbook

1. Finger millet planting dates for Soroti are borrowed from the MAAIF maize
   window. No Soroti millet calendar was found.
2. Finger millet maturity uses FAO EcoCrop's global range, not a Ugandan figure.
3. Rain needed per season uses EcoCrop's yearly ranges, because Soroti's rain
   behaves like one long season.
4. Rotation effects, beans before maize and the reverse, give a direction only,
   with no number.
5. Beans planting dates are national and Eastern region, not Soroti, and two
   pages of the manual do not match.

These five lines are also in `results/app_data.json`, in `crop_limitations` and
in `notes`, so the app can show them beside the crops.

## The water figure is not a sowing trigger

Every water row in the table is seasonal millimetres, carried under
`season_water_need_mm`. None is a planting rainfall threshold, and the app's
`rain_threshold_mm_10d` field is therefore null for every crop. The manuals say
only that planting follows the onset of rains and give no figure for it. A
seasonal total was not relabelled as a threshold, because that number would not
be the number the source states. Each crop card says both things: the threshold
is unknown, and the season water need is a seasonal total.

## Reading the columns

- `value` holds the figure as the source states it.
- `value_min` and `value_max` hold the numeric ends, so a script can read them.
- `page_or_quote` holds the page and the quoted line. Every sourced row has one.
- `basis` holds the reasoning, on assumed rows only.
- `note` holds a caveat, a disagreement or a scope limit.

Maize planting window `15/03 to 15/08` also carries day-of-year 74 and 227 in the
numeric columns. Those are 15 March and 15 August on a non-leap calendar. The
beans windows stay at month level, so they carry no day-of-year; a month cannot
be turned into one honest day.
