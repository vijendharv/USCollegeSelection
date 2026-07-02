"""Small local command-line interface used during development."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.config import Settings
from app.data import IPEDSDataSource, ScorecardDataSource
from app.demo import DemoError, run_offline_demo
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
    demo = commands.add_parser("demo", help="Run the complete demo without network access")
    demo.add_argument(
        "--profile",
        type=Path,
        default=Path("examples/demo-student-profile.json"),
        help="StudentProfile JSON file; defaults to the synthetic demo profile",
    )
    demo.add_argument(
        "--fixture",
        type=Path,
        help="Build a test database from a frozen Scorecard CSV instead of requiring real data",
    )
    demo.add_argument(
        "--database",
        type=Path,
        default=Path("data/college.duckdb"),
        help="Real local DuckDB database created by refresh-data",
    )
    demo.add_argument(
        "--output-dir",
        type=Path,
        default=Path("demo-output"),
        help="Root directory for generated report sessions",
    )
    demo.add_argument(
        "--schools-per-category",
        type=int,
        choices=range(1, 11),
        default=10,
        metavar="1-10",
        help="Maximum schools returned in each classification",
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
            scorecard = ScorecardDataSource(network, settings.raw_data_dir)
            download = scorecard.download_latest()
            field_download = scorecard.download_latest_field_of_study()
            ipeds_download = IPEDSDataSource(
                network, settings.raw_data_dir
            ).download_latest_completions()
        with DuckDBCollegeStore(settings.college_database_path, read_only=False) as store:
            report = store.refresh_from_scorecard_zip(
                download.archive_path,
                source_url=download.source_url,
                retrieved_at=download.retrieved_at,
                release_date=download.release_date,
                field_archive_path=field_download.archive_path,
                ipeds_archive_path=ipeds_download.archive_path,
                minimum_eligible_institutions=args.minimum_institutions,
            )
        print(report.model_dump_json())
        return 0

    if args.command == "demo":
        try:
            result = run_offline_demo(
                profile_path=args.profile,
                database_path=args.database,
                fixture_csv_path=args.fixture,
                output_root=args.output_dir,
                schools_per_category=args.schools_per_category,
            )
        except DemoError as exc:
            print(json.dumps({"status": "error", "message": str(exc)}, sort_keys=True))
            return 1
        print(json.dumps(result, sort_keys=True))
        return 0

    return 2
