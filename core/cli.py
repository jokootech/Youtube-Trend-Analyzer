"""Command Line Interface (CLI) argument parser for overriding Settings."""

from __future__ import annotations

import argparse
from config.settings import RunMode


def parse_cli_args() -> argparse.Namespace:
    """Parse optional command-line flags."""
    parser = argparse.ArgumentParser(description="YouTube Trend Analyzer Bot")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["scheduled", "once"],
        default=None,
        help="Override application run mode (scheduled or once)",
    )
    return parser.parse_args()