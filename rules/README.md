# Rules

`rules.csv` is the single source of truth for crop rules.

Conventions:

- Every row carries a tag in the `tag` column: `sourced`, `assumed` or `unknown`.
- A `sourced` row carries the source name, a link in `source_url`, the page and the
  quoted line in `page_or_quote`. The quote is copied as printed, never paraphrased.
- An `assumed` row carries its reasoning in `basis`. An `unknown` row carries no number.
- The app counts four parameters per crop: season length, water, pH and temperature.
  A crop appears only when at least three of the four have a `sourced` row. An
  `assumed` row is shown but never counts toward the cut.
- Unsourced numbers never enter the deliverables.

`docs/crop_rules.md` explains what the table supports, what it cannot, the two
later source corrections and the five limitation lines.

Sources: MAAIF maize training manual (2023), MAAIF beans training manual (2023),
FAO EcoCrop data sheets, National Research Council (1996) Lost Crops of Africa
Vol. I chapter 2, and the R8030 Final Technical Report. Full citations and links
go in `../SOURCES.md`.
