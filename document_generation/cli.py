from __future__ import annotations

import argparse
import json
from pathlib import Path

from .data_provider import CsaiDataProvider
from .generator import (
    DEFAULT_OUTPUT_DIR,
    _generate_one,
    generate_documents,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate AGM approval documents from CSAI databases."
    )
    parser.add_argument(
        "--company",
        action="append",
        required=True,
        help="Company name; repeat the option to generate multiple companies.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=None,
        help="Explicit template override; omit for automatic period-based selection.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--output",
        type=Path,
        help="Explicit output path; valid only when one --company is supplied.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.output and len(args.company) != 1:
        raise SystemExit("--output requires exactly one --company.")
    if args.output:
        results = [
            _generate_one(
                args.company[0],
                template_path=args.template,
                output_dir=args.output_dir,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
                provider=CsaiDataProvider(),
                explicit_output=args.output,
                ordinal_provider=lambda company: input(
                    f"{company} - AGM ordinal (e.g. THIRTEENTH; press Enter for generic): "
                ),
            )
        ]
    else:
        results = generate_documents(
            args.company,
            template_path=args.template,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            ordinal_provider=lambda company: input(
                f"{company} - AGM ordinal (e.g. THIRTEENTH; press Enter for generic): "
            ),
        )
    print(json.dumps([result.to_dict() for result in results], indent=2))
    return 0 if all(result.status in {"valid", "generated"} for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
