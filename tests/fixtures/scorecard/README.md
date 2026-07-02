# College Scorecard fixture

`institutions.csv` is a frozen, reduced-column extract of the public **Most Recent Institution-Level Data** published by the U.S. Department of Education College Scorecard.

- Source page: https://collegescorecard.ed.gov/data/
- Source archive: `Most-Recent-Cohorts-Institution_06102026.zip`
- Source last updated: 2026-06-10
- Fixture created: 2026-07-01

The rows and values are real public data. Only columns used by the initial DuckDB schema and a small set of institutions are retained so tests remain fast and offline. Pasadena City College verifies that institutions whose highest degree is below a bachelor's degree are excluded. Colegio Universitario de San Juan preserves a real negative net-price sentinel to verify that invalid costs become null.
