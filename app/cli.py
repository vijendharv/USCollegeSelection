"""Small local command-line interface used during development."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from app.config import Settings
from app.data import ScorecardDataSource
from app.logging_config import configure_logging
from app.networking import HttpClient
from app.storage import DuckDBCollegeStore


def health(settings: Settings) -> dict[str, Any]:
    """Validate local configuration and return a machine-readable health result."""
    settings.ensure_directories()
    return {
        "status": "ok",
        "service": "us-college-selection",
        "environment": settings.environment,
        "data_dir": str(settings.data_dir),
        "session_dir": str(settings.session_dir),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="us-college-selection")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("health", help="Validate local configuration")
    refresh = commands.add_parser("refresh-data", help="Refresh real College Scorecard data")
    refresh.add_argument(
        "--minimum-institutions",
        type=int,
        default=1_000,
        help="Fail when fewer eligible institutions are imported",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    configure_logging(settings.log_level)

    if args.command == "health":
        print(json.dumps(health(settings), sort_keys=True))
        return 0

    if args.command == "refresh-data":
        settings.ensure_directories()
        with HttpClient(
            timeout_seconds=settings.request_timeout_seconds,
            max_response_bytes=settings.max_download_bytes,
        ) as network:
            download = ScorecardDataSource(network, settings.raw_data_dir).download_latest()
        with DuckDBCollegeStore(settings.college_database_path, read_only=False) as store:
            report = store.refresh_from_scorecard_zip(
                download.archive_path,
                source_url=download.source_url,
                retrieved_at=download.retrieved_at,
                release_date=download.release_date,
                minimum_eligible_institutions=args.minimum_institutions,
            )
        print(report.model_dump_json())
        return 0

    return 2
