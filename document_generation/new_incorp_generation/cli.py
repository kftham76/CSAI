from __future__ import annotations

import argparse
import json
from pathlib import Path

from .generator import DEFAULT_OUTPUT_DIR, generate_new_incorp_documents


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the new-incorporation document batch.")
    parser.add_argument("--company", required=True, help="Company name to retrieve from new_incorp.db")
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview without writing documents")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing company batch atomically")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = generate_new_incorp_documents(
        args.company,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0 if result.status in {"generated", "dry_run"} else 1
