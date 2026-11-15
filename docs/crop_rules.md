# Crop rules — what the table holds and what it cannot support

Thirty-three rows, one per rule, in `rules/rules.csv`. Each row carries a tag:
`sourced`, `assumed` or `unknown`. A row is `sourced` only when it has a link,
a page and the line quoted as printed.

The app counts four parameters per crop: season length, water, pH and
temperature. A crop appears only when at least three of the four have a sourced
row. That rule is fixed in `docs/plan.md` and this table does not change it.

## What appears, and why

| Crop | Sourced of four | Unknown | Appears |
| --- | --- | --- | --- |
| Maize | 4 | none | yes |
| Common bean | 3 | water | yes |
| Finger millet | 3 | temperature | yes |
| Sorghum | 0 | all four | no, not in the table |
| Groundnut | 0 | all four | no, not in the table |

Sorghum and groundnut are not in the released table, so they are not in this
file and they do not appear in the app. The app shows the cut on its rules
coverage table, with the count of sourced rows beside it.

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

## Temperature

The workbook has no temperature row for any crop. Two manuals give one, and both
are quoted as printed, including their `oC` form:

- Maize, PDF page 8: "It is well adapted in warm condition with optimum
  temperature for plant growth ranges of 30oC – 34oC. Temperatures below 10oC
  and above 40oC result in poor growth and death of the maize plant."
- Beans, PDF page 9: "Beans thrives best in a warm climate of optimum growing
  temperature range of 20 to 28oC with a minimum of 15oC and a maximum of 32oC.
  Temperatures above 32oC and below 15oC will cause poor pod set resulting in
  yield loss."

Each is one row. The optimum range is the value; the outer limits sit in the note
of the same row. No temperature row was added for finger millet, because no
source opened for it gives one. Its temperature stays unknown.

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

## The water figure is not a 10-day trigger

Every water row in the table is seasonal millimetres. None is a 10-day rainfall
trigger, and the app's `rain_threshold_mm_10d` field is therefore null for every
crop. A seasonal total was not converted into a short-window trigger, because
that number would not be the number the source states.

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
