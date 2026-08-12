from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from docx import Document

from .generator import TEMPLATE_DIR


SOURCE_DIR = TEMPLATE_DIR / "source-originals"

SOURCE_CONTRACT = {
    "0. Beneficial Ownership - Letter to clients on changes (Hosay 3 Bakery).doc": ("818bf39050e77b5d282ef48286c6b6d11a9447e08ae1e371aa2c0e83e50f34f6", 4),
    "1. BO Notice & Reply to Shh  (Individual) - (Hosay 3 Bakery) - TWS.docx": ("88ec5cdc766ca567ace34ec0a3b20aaa29e19bf7e230dc31bc3a1ec341a571f5", 3),
    "Adopt Policy of BO Reporting (Hosay 3 Bakery).docx": ("d40e49e65685f2eb7cd59f90b620d4e1b5ac23a469f2b6ff47aa9c33f6a412ac", 5),
    "Disclosure_by_director_-_Tam Wee Seong.docx": ("8350134312fd61c835651cb3086810df777727ad2beff2df9acf6772a38ad9d9", 2),
    "Disclosure_by_member_-_Tam Wee Seong.docx": ("29c5b5de954e0403a5ae6f4e2edb7e01c8ddf273897f4cca8fffac13548e2f15", 2),
    "DWR - Accounting record kept (Hosay 3 Bakery).doc": ("dda4b708a0572d420ac05d6933ce175031a1e459bd147c54092459af78d52e2c", 2),
    "DWR - Appoint Secretary (Hosay 3 Bakery).docx": ("a41116715ba82b23128671742e76850cfdc0ea8dcd03aa58711d621b11eda9ef", 1),
    "DWR Authority to Lodge Beneficial Ownership (Hosay 3 Bakery).doc": ("8d636cd6aca087489fb677f621f775f59d62f52707f9dcce3e1eba8ccad43675", 1),
    "DWR_-_FBODM   dated 15 Oct 2024 (Hosay 3 Bakery).doc": ("e7fa27eeac804e0f9bce7050ec8a720bb76db35212c26c26a6f5e58c4814f8ed", 1),
    "Engagement Letter (Hosay 3 Bakery).docx": ("63b9e225a9b75dd8278627129f782e6d78eb4e5fe5849f04eb99b184945d4067", 2),
    "S236(3) Declaration by person before appointment as secretary  (Hosay 3 Bakery).docx": ("8b3a356bd2bfd1ff45e43751579d6bb9fbc2f915b90b8253ac1e7cea4c5974ac", 1),
}

BASE_PARTS = {
    "[Content_Types].xml", "_rels/.rels", "docProps/app.xml", "docProps/core.xml",
    "word/_rels/document.xml.rels", "word/document.xml", "word/fontTable.xml",
    "word/footer1.xml", "word/footer2.xml", "word/footer3.xml", "word/header1.xml",
    "word/header2.xml", "word/header3.xml", "word/settings.xml", "word/styles.xml",
    "word/theme/theme1.xml", "word/webSettings.xml",
}
STANDARD_PARTS = BASE_PARTS | {"word/endnotes.xml", "word/footnotes.xml", "word/numbering.xml"}
CUSTOM_XML_PARTS = {"customXml/_rels/item1.xml.rels", "customXml/item1.xml", "customXml/itemProps1.xml"}


def _markers(**values: int) -> Counter[str]:
    return Counter({"{{ " + key + " }}": count for key, count in values.items()})


TEMPLATE_CONTRACT = {
    "adopt_bo_policy_template.docx": ("62ce5c0d319d6ef752ee26d116b36ab2457aacbd97bbf493f0027d2279b10221", 3, 1, BASE_PARTS | {"word/numbering.xml"}, _markers(company_name=2, director_names_joined=1, director_signature_left=1, director_signature_right=1, incorporation_date=2, registration_no=1)),
    "bo_client_changes_letter_template.docx": ("cd250c002ecc720e4259edbd907c31dca9b8d49ccaebd12cfa09dbd334e5e889", 1, 1, STANDARD_PARTS, _markers(business_address_line_1=1, business_address_line_2=1, company_name=1, director_signature_left=1, director_signature_right=1, incorporation_date=1)),
    "bo_notice_reply_individual_template.docx": ("48862b1f44b62e3cc50ebf92b82d233422d159e3ca5127413dd0d0885bebba69", 2, 10, BASE_PARTS | CUSTOM_XML_PARTS | {"word/numbering.xml"}, _markers(answer_no_mark=1, answer_yes_mark=1, becoming_bo_date=1, company_name=5, criteria_a_mark=1, criteria_b_mark=1, criteria_c_mark=1, direct_category_mark=1, direct_percentage=2, director_signature_left=1, director_signature_right=1, individual_type_mark=1, member_address_compact_line_1=1, member_address_compact_line_2=1, member_address_title_line_1=1, member_address_title_line_2=1, member_address_title_line_3=1, member_dob=1, member_email=1, member_gender_title=1, member_id=2, member_name=5, member_nationality_title=2, member_occupation_title=2, member_phone=1, member_race_title=1, member_share_summary=1, registered_address_compact_line_1=1, registered_address_compact_line_2=1, registered_address_line_1=1, registered_address_line_2=1, registered_address_line_3=1, registration_no=4, share_fraction=2)),
    "disclosure_director_template.docx": ("3415b597de28ce375280ab460bac7b5047fc29961ec11b607be4cd59678e576c", 1, 1, STANDARD_PARTS | CUSTOM_XML_PARTS, _markers(business_address_upper=1, company_name=1, person_dob_upper=1, person_email=1, person_id=1, person_name=2, person_nationality_upper=1, person_occupation_upper=2, person_phone=1, person_race_upper=1, registration_no=1, residential_address_upper_line_1=1, residential_address_upper_line_2=1, residential_address_upper_line_3=1)),
    "disclosure_member_template.docx": ("772e550c7b9fce363307e3ee592b657bc15f6331ce2cf47e84caeeadf3e40113", 1, 1, STANDARD_PARTS, _markers(business_address_upper=1, company_name=1, person_dob_upper=1, person_email=1, person_id=1, person_name=2, person_nationality_upper=1, person_occupation_upper=1, person_phone=1, person_race_upper=1, registration_no=1, residential_address_upper_line_1=1, residential_address_upper_line_2=1, residential_address_upper_line_3=1)),
    "dwr_accounting_records_template.docx": ("2897bf359f1c37572ce7147b14dac8f4d55628b745768ed7169fcdafdbd37d54", 1, 3, STANDARD_PARTS, _markers(business_address=2, business_address_line_1=1, business_address_line_2=2, company_name=3, director_signature_left=2, director_signature_right=2, registration_no=2)),
    "dwr_appoint_secretary_template.docx": ("9bc353b8d161058a256cec4d85709fc4266d2efc275df92f97c9b3246063ca3c", 1, 1, BASE_PARTS | CUSTOM_XML_PARTS | {"docProps/custom.xml", "word/endnotes.xml", "word/footnotes.xml"}, _markers(company_name=1, director_signature_left=1, director_signature_right=1, incorporation_date=1, registration_no=1)),
    "dwr_authority_bo_template.docx": ("1844507b91e54a90fd74cf935d20ba87a24a03c015da0245cb2c584ac37d7a66", 1, 1, STANDARD_PARTS, _markers(company_name=1, director_signature_left=1, director_signature_right=1, registration_no=1)),
    "dwr_first_board_meeting_template.docx": ("8ec6bee8d37aa20bdc95e8f1c7d816cd315a915f7417f46ead75ab112cc166b2", 1, 1, BASE_PARTS | {"docProps/custom.xml"}, _markers(company_name=1, director_names_sentence=1, director_signature_left=1, director_signature_right=1, incorporation_date=2, registered_address=1, registration_no=2, subscriber_rows=1)),
    "engagement_letter_template.docx": ("684643eb76b61467d8e4e17ba3f80474f15c032015f76f1628f00b1c75cea0b1", 1, 0, BASE_PARTS | {"word/numbering.xml"}, _markers(business_address_line_1=1, business_address_line_2=1, business_address_line_3=1, company_name=3, director1_name=1, incorporation_date=1)),
    "s236_secretary_declaration_template.docx": ("01007574926273adcb27a606cfa7cd08363241df57c488e27b48662a1316def1", 1, 2, STANDARD_PARTS, _markers(company_name=2, incorporation_date_upper=2, registration_no=1)),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _marker_inventory(path: Path) -> Counter[str]:
    with ZipFile(path) as package:
        xml = "".join(
            package.read(name).decode("utf-8", "ignore")
            for name in package.namelist()
            if name.startswith("word/") and name.endswith(".xml")
        )
    return Counter(re.findall(r"\{\{[^{}]+\}\}", xml))


def audit_templates() -> dict[str, object]:
    errors: list[str] = []
    for name, (expected_hash, _pages) in SOURCE_CONTRACT.items():
        path = SOURCE_DIR / name
        if not path.is_file() or _sha256(path) != expected_hash:
            errors.append(f"Source authority changed or is missing: {name}")
    for name, (expected_hash, sections, tables, parts, markers) in TEMPLATE_CONTRACT.items():
        path = TEMPLATE_DIR / name
        if not path.is_file():
            errors.append(f"Production template is missing: {name}")
            continue
        document = Document(path)
        with ZipFile(path) as package:
            actual_parts = set(package.namelist())
        if _sha256(path) != expected_hash:
            errors.append(f"Template hash changed: {name}")
        if (len(document.sections), len(document.tables)) != (sections, tables):
            errors.append(f"Template section/table geometry changed: {name}")
        if actual_parts != parts:
            errors.append(f"Template package-part inventory changed: {name}")
        if _marker_inventory(path) != markers:
            errors.append(f"Template marker inventory changed: {name}")
    return {"valid": not errors, "errors": errors, "source_count": len(SOURCE_CONTRACT), "template_count": len(TEMPLATE_CONTRACT)}


def main() -> int:
    result = audit_templates()
    print(result)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
