# College Scorecard fixture

The fixture contains reduced-column extracts of the public College Scorecard and IPEDS sources:

- `institutions.csv` — institution records and two-digit `PCIPxx` shares;
- `fields.csv` — four-digit bachelor field-of-study outcomes shaped like the current Scorecard file; and
- `ipeds-completions.csv` — six-digit bachelor completion records shaped like IPEDS `C2024_A`.

- Source page: https://collegescorecard.ed.gov/data/
- Source archive: `Most-Recent-Cohorts-Institution_06102026.zip`
- Source last updated: 2026-06-10
- Fixture created: 2026-07-01
- IPEDS source: https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx (`C2024_A`)

The rows and values are real public data. Only columns used by the initial DuckDB schema and a small set of institutions are retained so tests remain fast and offline. Pasadena City College verifies that institutions whose highest degree is below a bachelor's degree are excluded. UC College of the Law San Francisco verifies that graduate-only institutions with no undergraduate enrollment are excluded. Colegio Universitario de San Juan preserves a real negative net-price sentinel to verify that invalid costs become null.
