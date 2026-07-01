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

## Documentation

- [Product specification](PRODUCT_SPEC.md)
- [Architecture](ARCHITECTURE.md)
