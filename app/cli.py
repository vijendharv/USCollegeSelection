"""Small local command-line interface used during development."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from app.config import Settings
from app.logging_config import configure_logging


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
    parser.add_argument("command", choices=("health",))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    configure_logging(settings.log_level)

    if args.command == "health":
        print(json.dumps(health(settings), sort_keys=True))
        return 0

    return 2
