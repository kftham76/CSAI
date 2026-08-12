from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .context_builder import build_document_context, context_preview
from .data_provider import CsaiDataProvider, DataProvider
from .models import DocumentContext, GenerationResult, Section90Details, ValidationIssue
from .output_validation import validate_output_docx
from .renderer import render_document
from .rotation_reader import (
    DEFAULT_CLIENTS_ROOT,
    discover_rotation_workbook,
    read_retiring_directors,
)
from .template_selection import (
    TEMPLATE_FIRST_AGM,
    TEMPLATE_SECTION_90,
    TEMPLATE_STANDARD_OR_FIRST_AGM,
    infer_override_family,
)
from .text_utils import clean_text, normalize_identity, safe_filename


DEFAULT_TEMPLATE = (
    Path(__file__).resolve().parent.parent
    / "templates"
    / "agm"
    / "agm_approve_accounts_template.docx"
)
FIRST_AGM_TEMPLATE = (
    Path(__file__).resolve().parent.parent
    / "templates"
    / "agm"
    / "first_agm_approve_accounts_template.docx"
)
SECTION_90_TEMPLATE = (
    Path(__file__).resolve().parent.parent
    / "templates"
    / "agm"
    / "agm_approve_accounts_template_section_90.docx"
)
# Backwards-compatible public name used by existing callers/tests.
IRREGULAR_YEAR_TEMPLATE = FIRST_AGM_TEMPLATE
REGULAR_YEAR_MIN_DAYS = 364
REGULAR_YEAR_MAX_DAYS = 367
DEFAULT_OUTPUT_DIR = Path(r"D:\CSAI_DATA\AGM Output")


def resolve_template_path(
    context: DocumentContext,
    template_path: Path | None = None,
) -> Path:
    """Resolve the template for one validated company context."""
    if template_path is not None:
        return Path(template_path)
    if context.template_family == TEMPLATE_SECTION_90:
        return SECTION_90_TEMPLATE
    if context.template_family in {
        TEMPLATE_STANDARD_OR_FIRST_AGM,
        TEMPLATE_FIRST_AGM,
    }:
        span_days = (context.financial_year_end - context.financial_year_start).days
        if span_days < REGULAR_YEAR_MIN_DAYS or span_days > REGULAR_YEAR_MAX_DAYS:
            return FIRST_AGM_TEMPLATE
    return DEFAULT_TEMPLATE


def _section90_details(
    context: DocumentContext,
    ordinal: str,
    clients_root: Path,
) -> tuple[Section90Details | None, list[ValidationIssue]]:
    workbook, issues = discover_rotation_workbook(
        context.company_folder,
        context.circulation_date.year,
        clients_root,
    )
    if workbook is None:
        return None, issues
    retiring, read_issues = read_retiring_directors(
        workbook,
        context.financial_year_end.year,
        context.directors,
    )
    if read_issues:
        return None, read_issues
    meeting_date = context.circulation_date
    return Section90Details(
        agm_ordinal=clean_text(ordinal).upper(),
        meeting_date=meeting_date,
        notice_date=meeting_date - timedelta(days=18),
        letter_date=meeting_date,
        venue_lines=(
            "428, Jalan Legenda 26,",
            "Legenda Heights,",
            "08000 Sungai Petani, Kedah",
        ),
        meeting_start_time="9.30 a.m.",
        meeting_end_time="9.45 a.m.",
        retiring_directors=retiring,
        rotation_workbook_path=workbook,
    ), []


def default_output_path(company_name: str, fye, circulation_date, output_dir: Path) -> Path:
    fye_text = fye.strftime("%d.%m.%Y")
    filename = (
        f"{company_name} - Approve Accounts YE{fye_text} "
        f"({circulation_date.year}).docx"
    )
    return output_dir / safe_filename(filename)


def _generate_one(
    company_name: str,
    *,
    template_path: Path | None,
    output_dir: Path,
    overwrite: bool,
    dry_run: bool,
    provider: DataProvider,
    explicit_output: Path | None = None,
    section90_ordinal: str | None = None,
    ordinal_provider: Callable[[str], str] | None = None,
    clients_root: Path = DEFAULT_CLIENTS_ROOT,
) -> GenerationResult:
    build = build_document_context(company_name, provider)
    if not build.valid or build.context is None:
        return GenerationResult(
            company=company_name,
            status="invalid",
            issues=build.issues,
        )
    context = build.context
    if template_path is not None:
        override_family = infer_override_family(
            Path(template_path), context.template_family
        )
        if override_family != context.template_family:
            build = build_document_context(company_name, provider, override_family)
            if not build.valid or build.context is None:
                return GenerationResult(
                    company=company_name,
                    status="invalid",
                    issues=build.issues,
                )
            context = build.context
    selected_template = resolve_template_path(context, template_path)
    prompt_required = (
        context.template_family == TEMPLATE_SECTION_90
        and section90_ordinal is None
    )
    if context.template_family == TEMPLATE_SECTION_90:
        ordinal = section90_ordinal
        if ordinal is None and not dry_run and ordinal_provider is not None:
            ordinal = ordinal_provider(context.company_name)
        details, detail_issues = _section90_details(
            context,
            ordinal or "",
            Path(clients_root),
        )
        if detail_issues or details is None:
            return GenerationResult(
                company=context.company_name,
                status="invalid",
                issues=detail_issues,
            )
        context.section90 = details
    preview = context_preview(context)
    preview["selected_template_path"] = str(selected_template)
    preview["agm_ordinal_prompt_required"] = prompt_required
    if context.section90 is not None:
        preview.update(
            {
                "agm_ordinal": context.section90.agm_ordinal,
                "meeting_date": context.section90.meeting_date.isoformat(),
                "notice_date": context.section90.notice_date.isoformat(),
                "letter_date": context.section90.letter_date.isoformat(),
                "retiring_directors": [p.name for p in context.section90.retiring_directors],
                "rotation_workbook_path": str(context.section90.rotation_workbook_path),
            }
        )
    if dry_run:
        return GenerationResult(
            company=context.company_name,
            status="valid",
            preview=preview,
        )
    if not selected_template.is_file():
        return GenerationResult(
            company=context.company_name,
            status="error",
            issues=[
                ValidationIssue(
                    code="template_not_found",
                    message=f"Production template was not found: {selected_template}",
                    source="template",
                )
            ],
            preview=preview,
        )
    output_path = explicit_output or default_output_path(
        context.company_name,
        context.financial_year_end,
        context.circulation_date,
        output_dir,
    )
    if output_path.exists() and not overwrite:
        return GenerationResult(
            company=context.company_name,
            status="invalid",
            issues=[
                ValidationIssue(
                    code="output_exists",
                    message=f"Output already exists: {output_path}",
                    source="output",
                )
            ],
            preview=preview,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        handle = tempfile.NamedTemporaryFile(
            prefix="agm-generation-",
            suffix=".docx",
            dir=output_path.parent,
            delete=False,
        )
        temporary_path = Path(handle.name)
        handle.close()
        render_document(selected_template, temporary_path, context)
        issues = validate_output_docx(temporary_path, context.template_family)
        if issues:
            temporary_path.unlink(missing_ok=True)
            return GenerationResult(
                company=context.company_name,
                status="error",
                issues=issues,
                preview=preview,
            )
        temporary_path.replace(output_path)
        return GenerationResult(
            company=context.company_name,
            status="generated",
            output_path=output_path,
            preview=preview,
        )
    except Exception as error:  # pragma: no cover - surfaced as user-facing result
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        return GenerationResult(
            company=context.company_name,
            status="error",
            issues=[
                ValidationIssue(
                    code="generation_failed",
                    message=str(error),
                    source="renderer",
                )
            ],
            preview=preview,
        )


def generate_documents(
    company_names: Sequence[str],
    template_path: Path | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    overwrite: bool = False,
    dry_run: bool = False,
    *,
    provider: DataProvider | None = None,
    section90_inputs: Mapping[str, str] | None = None,
    ordinal_provider: Callable[[str], str] | None = None,
    clients_root: Path = DEFAULT_CLIENTS_ROOT,
) -> list[GenerationResult]:
    data_provider = provider or CsaiDataProvider()
    normalized_inputs = {
        normalize_identity(name): value for name, value in (section90_inputs or {}).items()
    }
    return [
        _generate_one(
            company_name,
            template_path=Path(template_path) if template_path is not None else None,
            output_dir=Path(output_dir),
            overwrite=overwrite,
            dry_run=dry_run,
            provider=data_provider,
            section90_ordinal=normalized_inputs.get(normalize_identity(company_name)),
            ordinal_provider=ordinal_provider,
            clients_root=clients_root,
        )
        for company_name in company_names
    ]
