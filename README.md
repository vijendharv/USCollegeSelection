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

The demo runs on your computer and uses the full real College Scorecard database. No cloud deployment or paid service is involved.

First install dependencies and download the real public data once:

```bash
uv sync --all-groups
uv run python -m app refresh-data
```

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

The JSON, PDF, and Excel workbook are generated from the same canonical report. By default, the demo returns up to ten schools per Safety / Likely, Target, Reach, and Insufficient Data category when enough defensible results exist.

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
- Many institutions do not report compatible GPA or test-score ranges, so they may be labeled Insufficient Data.
- Major-specific admissions selectivity, current deadlines, fees, and supplements are not yet populated.
- Transcript and résumé PDF parsing begins in Stage 2; Milestone 1.7 accepts confirmed profile JSON.

## Documentation

- [Product specification](PRODUCT_SPEC.md)
- [Architecture](ARCHITECTURE.md)
- [Milestone implementation records](docs/milestones/README.md)
