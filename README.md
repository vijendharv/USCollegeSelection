# US College Selection

An explainable college-search and gap-analysis application designed for ChatGPT.

## Milestone 1.1: project foundation

This milestone provides the Python package, configuration, structured logging, a local health command, and explicit networking and storage boundaries.

### Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)

### Setup

```bash
uv sync --all-groups
```

### Verify the project

The complete Milestone 1.1 test suite runs with one command:

```bash
uv run pytest
```

Run all static checks with:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
```

### Health command

```bash
uv run python -m app health
```

Configuration uses environment variables prefixed with `USCS_`:

```bash
USCS_LOG_LEVEL=DEBUG uv run python -m app health
```

The command creates configured local data and session directories when needed and returns a JSON health response.

### Refresh real College Scorecard data

```bash
uv run python -m app refresh-data
```

The command discovers the current official institution archive from the College Scorecard data page, downloads it under `data/raw/`, validates it, and atomically builds `data/college.duckdb`. Both the downloaded archive and generated database are local artifacts excluded from Git.

## Run the complete demo locally

The demo runs on your computer and uses the full real College Scorecard database. No cloud deployment or paid service is involved. Results are fit-ranked separately for each intended major rather than selected alphabetically. Each exact six-digit CIP match also receives a student-specific national fit position across the eligible US institutions analyzed; this is an internal evidence-based rank, not a commercial prestige ranking.

First install dependencies and download the real public data once:

```bash
uv sync --all-groups
uv run python -m app refresh-data
```

Run `refresh-data` again after upgrading. Database schema version 3 combines the institution and four-digit field-of-study College Scorecard archives with six-digit IPEDS bachelor-completion data. The three official downloads happen only during refresh; ranking remains local and offline.

Then run the demo using the included synthetic student profile:

```bash
uv run python -m app demo
```

After `refresh-data` succeeds, the `demo` command itself performs no network calls. It prints a JSON summary containing the generated output directory. That private session directory contains:

```text
college-report.json
college-report.pdf
college-report.xlsx
```

The JSON, PDF, and Excel workbook are generated from the same canonical report. Profiles must contain one to three intended majors in priority order. By default, the demo returns the highest student-major fit results in each Safety / Likely, Target, Reach, and Insufficient Data category, up to ten per category when enough defensible results exist; it never samples randomly or takes schools alphabetically. Admissions categories remain institution-level; both the national fit position and the within-category fit rank are major-specific. Student-supplied colleges are retained and shown in a separate table before generated recommendations.

To test another student, copy the example, edit it, and supply its path:

```bash
cp examples/demo-student-profile.json my-student-profile.json
uv run python -m app demo --profile my-student-profile.json
```

Keep real student profiles outside Git. To return fewer schools per category:

```bash
uv run python -m app demo --schools-per-category 5
```

### Verify the offline path without downloading the full dataset

This command is only a quick engineering test. It explicitly builds a tiny database from the frozen public fixture and does not represent the real nationwide demo:

```bash
uv run python -m app demo \
  --fixture tests/fixtures/scorecard/institutions.csv \
  --database /tmp/uscs-demo/college.duckdb \
  --output-dir /tmp/uscs-demo/output
```

### Current demo limitations

- College Scorecard is the latest available annual federal data, not live admissions data.
- ACT composite ranges are shown and used when reported. College Scorecard does not provide admitted-student high-school GPA ranges, so the report labels that benchmark as unavailable from the current official dataset instead of implying a failed download.
- A school may be labeled Insufficient Data when no compatible GPA or submitted SAT/ACT comparison is available.
- Major-specific admissions selectivity, current deadlines, fees, and supplements are not yet populated.
- Exact program availability uses six-digit IPEDS CIP data; ranking evidence uses four-digit Scorecard field-of-study outcomes and falls back to two-digit families when finer data is missing. None of these sources proves direct admission, program capacity, or program-specific selectivity.
- Transcript and résumé PDF parsing begins in Stage 2; Milestone 1.7 accepts confirmed profile JSON.

## Documentation

- [Product specification](PRODUCT_SPEC.md)
- [Architecture](ARCHITECTURE.md)
- [Milestone implementation records](docs/milestones/README.md)
