from __future__ import annotations

import re
import tempfile
from pathlib import Path

from .context_builder import context_from_draft, context_preview
from .data_provider import CsaiPreIncorpDataProvider, DataProvider
from .models import PreIncorpDraft, PreIncorpGenerationResult, ValidationIssue
from .output_validation import validate_pre_incorp_docx
from .preparation import prepare_pre_incorp_generation
from .renderer import render_notice, render_s201


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
S201_TEMPLATE = PACKAGE_ROOT / "templates" / "pre-incorp" / "Pre incorp. S201 and declaration Hosay 3 Bakery-THK.docx"
NOTICE_TEMPLATE = PACKAGE_ROOT / "templates" / "pre-incorp" / "pre_incorp_Director's_Notice_under_S57,_S219_&_S221.(Hosay 3 Bakery) THK.docx"
DEFAULT_OUTPUT_DIR = Path(r"D:\CSAI_DATA\pre-incorp Output")


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip().rstrip(".")
    return cleaned or "unnamed"


def _target_paths(company_name: str, directors, output_dir: Path) -> list[tuple[str, object, Path]]:
    company_dir = output_dir / safe_filename(company_name)
    targets: list[tuple[str, object, Path]] = []
    for director in directors:
        name = safe_filename(director.name)
        targets.extend(
            (
                ("s201", director, company_dir / f"{name} - Pre-incorp S201 and Declaration.docx"),
                ("notice", director, company_dir / f"{name} - Director's Notice S57 S219 S221.docx"),
            )
        )
    return targets


def generate_pre_incorp_documents(
    company_name: str,
    reference_no: str | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    overwrite: bool = False,
    dry_run: bool = False,
    *,
    provider: DataProvider | None = None,
    draft: PreIncorpDraft | None = None,
    confirmed: bool = False,
) -> PreIncorpGenerationResult:
    data_provider = provider or CsaiPreIncorpDataProvider()
    if draft is None:
        prepared = prepare_pre_incorp_generation(company_name, data_provider)
        if prepared.draft is None:
            return PreIncorpGenerationResult(
                company=company_name,
                status="invalid",
                issues=prepared.issues,
            )
        draft = prepared.draft

    build = context_from_draft(draft)
    draft_preview = draft.to_dict()
    if not build.valid or build.context is None:
        status = "input_required" if dry_run and draft.required_inputs() else "invalid"
        return PreIncorpGenerationResult(
            company=company_name,
            status=status,
            issues=build.issues,
            preview={
                "draft": draft_preview,
                "reference_no": str(reference_no or "").strip() or None,
                "reference_no_prompt_required": not bool(str(reference_no or "").strip()),
            },
        )

    context = build.context
    reference = str(reference_no or "").strip()
    output_root = Path(output_dir)
    targets = _target_paths(context.company_name, context.directors, output_root)
    preview = context_preview(context)
    preview.update(
        {
            "draft": draft_preview,
            "reference_no": reference or None,
            "reference_no_prompt_required": not bool(reference),
            "s201_template_path": str(S201_TEMPLATE),
            "notice_template_path": str(NOTICE_TEMPLATE),
            "output_paths": [str(target) for _, _, target in targets],
        }
    )
    if dry_run:
        status = "input_required" if draft.required_inputs() or not reference else "valid"
        return PreIncorpGenerationResult(company=context.company_name, status=status, preview=preview)
    if draft.required_inputs() and not confirmed:
        return PreIncorpGenerationResult(
            company=context.company_name,
            status="input_required",
            issues=[
                ValidationIssue(
                    "draft_confirmation_required",
                    "The retrieved draft contains provisional or conflicting values that require confirmation.",
                    "hybrid draft",
                )
            ],
            preview=preview,
        )
    if not reference:
        return PreIncorpGenerationResult(
            company=context.company_name,
            status="input_required",
            issues=[ValidationIssue("missing_reference_no", "Reference No. is required.", "terminal input")],
            preview=preview,
        )
    missing_templates = [path for path in (S201_TEMPLATE, NOTICE_TEMPLATE) if not path.is_file()]
    if missing_templates:
        return PreIncorpGenerationResult(
            company=context.company_name,
            status="error",
            issues=[ValidationIssue("template_not_found", f"Template was not found: {path}", "template") for path in missing_templates],
            preview=preview,
        )
    collisions = [target for _, _, target in targets if target.exists()]
    if collisions and not overwrite:
        return PreIncorpGenerationResult(
            company=context.company_name,
            status="invalid",
            issues=[ValidationIssue("output_exists", f"Output already exists: {path}", "output") for path in collisions],
            preview=preview,
        )

    company_dir = targets[0][2].parent
    company_dir.parent.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path]] = []
    try:
        with tempfile.TemporaryDirectory(prefix="pre-incorp-generation-", dir=company_dir.parent) as temporary:
            staging_dir = Path(temporary)
            for kind, director, target in targets:
                staged_path = staging_dir / target.name
                if kind == "s201":
                    render_s201(S201_TEMPLATE, staged_path, context, director, reference)
                    template = S201_TEMPLATE
                else:
                    render_notice(NOTICE_TEMPLATE, staged_path, context, director)
                    template = NOTICE_TEMPLATE
                issues = validate_pre_incorp_docx(
                    staged_path,
                    template,
                    kind,
                    context,
                    director,
                    reference,
                )
                if issues:
                    return PreIncorpGenerationResult(
                        company=context.company_name,
                        status="error",
                        issues=issues,
                        preview=preview,
                    )
                staged.append((staged_path, target))

            company_dir.mkdir(parents=True, exist_ok=True)
            backup_dir = staging_dir / "backups"
            backup_dir.mkdir()
            backups: list[tuple[Path, Path]] = []
            published: list[Path] = []
            try:
                for _, target in staged:
                    if target.exists():
                        backup = backup_dir / target.name
                        target.replace(backup)
                        backups.append((backup, target))
                for source, target in staged:
                    source.replace(target)
                    published.append(target)
            except Exception:
                for target in published:
                    target.unlink(missing_ok=True)
                for backup, target in backups:
                    backup.replace(target)
                raise
    except Exception as error:
        return PreIncorpGenerationResult(
            company=context.company_name,
            status="error",
            issues=[ValidationIssue("generation_failed", str(error), "renderer")],
            preview=preview,
        )
    return PreIncorpGenerationResult(
        company=context.company_name,
        status="generated",
        output_paths=[target for _, _, target in targets],
        preview=preview,
    )
