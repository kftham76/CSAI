from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .generator import DEFAULT_OUTPUT_DIR, generate_pre_incorp_documents
from .interactive import complete_interactively, display_draft
from .models import PreIncorpGenerationResult, ValidationIssue
from .preparation import prepare_pre_incorp_generation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate pre-incorporation director documents from CSAI data."
    )
    parser.add_argument("--company", required=True, help="Exactly one company name.")
    parser.add_argument(
        "--reference-no",
        default=None,
        help="Company Reference No.; prompted for normal interactive runs when omitted.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _print_result(result: PreIncorpGenerationResult) -> None:
    print(json.dumps(result.to_dict(), indent=2))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    prepared = prepare_pre_incorp_generation(args.company)
    if prepared.draft is None:
        result = PreIncorpGenerationResult(
            company=args.company,
            status="invalid",
            issues=prepared.issues,
        )
        _print_result(result)
        return 1

    draft = prepared.draft
    if args.dry_run:
        result = generate_pre_incorp_documents(
            args.company,
            reference_no=args.reference_no,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            dry_run=True,
            draft=draft,
        )
        _print_result(result)
        return 0 if result.status == "valid" else 1

    if not sys.stdin.isatty():
        display_draft(draft, print)
        if args.reference_no:
            result = generate_pre_incorp_documents(
                args.company,
                reference_no=args.reference_no,
                output_dir=args.output_dir,
                overwrite=args.overwrite,
                draft=draft,
                confirmed=True,
            )
            _print_result(result)
            return 0 if result.status == "generated" else 1

        preview_result = generate_pre_incorp_documents(
            args.company,
            reference_no=None,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            dry_run=True,
            draft=draft,
        )
        preview_result.status = "input_required"
        preview_result.issues.append(
            ValidationIssue(
                "missing_reference_no",
                "Reference No. is required; supply --reference-no in a non-interactive terminal.",
                "terminal input",
            )
        )
        _print_result(preview_result)
        return 1

    _, reference_no = complete_interactively(draft, args.reference_no, input, print)

    result = generate_pre_incorp_documents(
        args.company,
        reference_no=reference_no,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
        draft=draft,
        confirmed=True,
    )
    _print_result(result)
    return 0 if result.status == "generated" else 1
