from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .context_builder import context_preview, prepare_new_incorp_generation
from .data_provider import DataProvider
from .models import NewIncorpContext, NewIncorpGenerationResult, PersonContext, ValidationIssue
from .output_validation import validate_output_docx
from .renderer import render_template
from .value_utils import safe_filename


DEFAULT_OUTPUT_DIR = Path(r"D:\CSAI_DATA\new-incorp-output")
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "new_incorp"


@dataclass(frozen=True)
class DocumentJob:
    template_name: str
    output_name: str
    person: PersonContext | None = None


COMPANY_DOCUMENTS = (
    ("s236_secretary_declaration_template.docx", "S236(3) Secretary Declaration.docx"),
    ("bo_client_changes_letter_template.docx", "Beneficial Ownership - Client Changes Letter.docx"),
    ("adopt_bo_policy_template.docx", "Adopt Policy of BO Reporting.docx"),
    ("dwr_accounting_records_template.docx", "DWR - Accounting Records Kept.docx"),
    ("dwr_appoint_secretary_template.docx", "DWR - Appoint Secretary.docx"),
    ("dwr_authority_bo_template.docx", "DWR - Authority to Lodge Beneficial Ownership.docx"),
    ("dwr_first_board_meeting_template.docx", "DWR - First Board Meeting.docx"),
    ("engagement_letter_template.docx", "Engagement Letter.docx"),
)


def _jobs(context: NewIncorpContext) -> list[DocumentJob]:
    jobs = [DocumentJob(template, output) for template, output in COMPANY_DOCUMENTS]
    for member in context.members:
        person_name = safe_filename(member.name)
        jobs.extend(
            (
                DocumentJob("bo_notice_reply_individual_template.docx", f"BO Notice & Reply - {person_name}.docx", member),
                DocumentJob("disclosure_member_template.docx", f"Disclosure by Member - {person_name}.docx", member),
            )
        )
    for director in context.directors:
        jobs.append(
            DocumentJob(
                "disclosure_director_template.docx",
                f"Disclosure by Director - {safe_filename(director.name)}.docx",
                director,
            )
        )
    return jobs


def _preview(context: NewIncorpContext, target_dir: Path, jobs: list[DocumentJob]) -> dict:
    preview = context_preview(context)
    preview["output_directory"] = str(target_dir)
    preview["output_paths"] = [str(target_dir / job.output_name) for job in jobs]
    return preview


def _publish(staged_dir: Path, target_dir: Path, overwrite: bool) -> None:
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if target_dir.exists() and not overwrite:
        raise FileExistsError(f"Output directory already exists: {target_dir}")
    backup = target_dir.with_name(f".{target_dir.name}.backup-{uuid4().hex}")
    moved_existing = False
    try:
        if target_dir.exists():
            target_dir.replace(backup)
            moved_existing = True
        staged_dir.replace(target_dir)
        if moved_existing:
            shutil.rmtree(backup)
    except Exception:
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        if moved_existing and backup.exists():
            backup.replace(target_dir)
        raise


def generate_new_incorp_documents(
    company_name: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    overwrite: bool = False,
    dry_run: bool = False,
    provider: DataProvider | None = None,
) -> NewIncorpGenerationResult:
    prepared = prepare_new_incorp_generation(company_name, provider=provider)
    if not prepared.valid or prepared.context is None:
        return NewIncorpGenerationResult(company=company_name, status="invalid", issues=prepared.issues)

    context = prepared.context
    output_root = Path(output_dir)
    target_dir = output_root / safe_filename(context.company_name)
    jobs = _jobs(context)
    targets = [target_dir / job.output_name for job in jobs]
    preview = _preview(context, target_dir, jobs)

    missing_templates = [job.template_name for job in jobs if not (TEMPLATE_DIR / job.template_name).is_file()]
    if missing_templates:
        return NewIncorpGenerationResult(
            company=context.company_name,
            status="invalid",
            output_paths=targets,
            issues=[
                ValidationIssue("missing_template", "Required template is missing: " + name, "templates/new_incorp")
                for name in sorted(set(missing_templates))
            ],
            preview=preview,
        )

    if dry_run:
        return NewIncorpGenerationResult(
            company=context.company_name,
            status="dry_run",
            output_paths=targets,
            preview=preview,
        )

    if target_dir.exists() and not overwrite:
        return NewIncorpGenerationResult(
            company=context.company_name,
            status="collision",
            output_paths=targets,
            issues=[ValidationIssue("output_collision", f"Output directory already exists: {target_dir}", "output")],
            preview=preview,
        )

    output_root.mkdir(parents=True, exist_ok=True)
    temporary_root = output_root / f".new-incorp-stage-{uuid4().hex}"
    temporary_root.mkdir()
    staged_company = temporary_root / safe_filename(context.company_name)
    staged_company.mkdir()
    try:
        validation_issues: list[ValidationIssue] = []
        for job in jobs:
            staged_path = staged_company / job.output_name
            try:
                render_template(TEMPLATE_DIR / job.template_name, staged_path, context, job.person)
            except Exception as error:
                raise RuntimeError(f"{job.output_name}: {error}") from error
            validation_issues.extend(
                validate_output_docx(
                    staged_path,
                    context,
                    require_registration_no=job.template_name
                    not in {"bo_client_changes_letter_template.docx", "engagement_letter_template.docx"},
                )
            )
        if validation_issues:
            return NewIncorpGenerationResult(
                company=context.company_name,
                status="invalid",
                output_paths=targets,
                issues=validation_issues,
                preview=preview,
            )
        _publish(staged_company, target_dir, overwrite)
        return NewIncorpGenerationResult(
            company=context.company_name,
            status="generated",
            output_paths=targets,
            preview=preview,
        )
    except Exception as error:
        return NewIncorpGenerationResult(
            company=context.company_name,
            status="error",
            output_paths=targets,
            issues=[ValidationIssue("generation_failed", str(error), "generator")],
            preview=preview,
        )
    finally:
        if temporary_root.exists():
            shutil.rmtree(temporary_root, ignore_errors=True)
