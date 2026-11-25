"""Command-line entry point: python -m pipeline.cli --mode incremental|backfill."""

import argparse
import logging
import sys
from datetime import date

from pipeline.config import load_settings
from pipeline.pipeline import run_pipeline


def parse_args(argv=None):
    """Parse and validate CLI arguments. --to is exclusive: window is [from, to)."""
    parser = argparse.ArgumentParser(prog="pipeline")
    parser.add_argument("--mode", choices=["incremental", "backfill"], required=True)
    parser.add_argument("--from", dest="date_from", type=date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument(
        "--to",
        dest="date_to",
        type=date.fromisoformat,
        help="YYYY-MM-DD, exclusive",
    )
    args = parser.parse_args(argv)

    if args.mode == "backfill" and not (args.date_from and args.date_to):
        parser.error("backfill requires --from and --to")
    if args.date_from and args.date_to and args.date_from >= args.date_to:
        parser.error("--from must be earlier than --to")
    return args


def main(argv=None):
    """Run the pipeline once. Exit code 0 on success, 1 on failure."""
    args = parse_args(argv)
    settings = load_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        run_pipeline(settings, args.mode, args.date_from, args.date_to)
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
