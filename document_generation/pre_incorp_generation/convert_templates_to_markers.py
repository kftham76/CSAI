from __future__ import annotations

import hashlib
import os
import shutil
from collections import Counter
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W_NS}
W = f"{{{W_NS}}}"

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "pre-incorp"
BACKUP_DIR = TEMPLATE_DIR / "originals-before-marker-conversion"
S201_FILENAME = "Pre incorp. S201 and declaration Hosay 3 Bakery-THK.docx"
NOTICE_FILENAME = (
    "pre_incorp_Director's_Notice_under_S57,_S219_&_S221."
    "(Hosay 3 Bakery) THK.docx"
)

ORIGINAL_HASHES = {
    S201_FILENAME: "98ffb593cc0341e85fdf94c06a3175aee92c7123a639f7ba86d4ad7d1d60989e",
    NOTICE_FILENAME: "4f855fe3b840c8f4298a2c0a7fbe3c674bb0977f9028c4a787f80c24fd4efcf2",
}

S201_MARKERS = Counter(
    {
        "{{ reference_no }}": 1,
        "{{ company_name }}": 4,
        "{{ director_name }}": 2,
        "{{ identification_label }}": 2,
        "{{ director_id }}": 2,
        "{{ declaration_date }}": 2,
        "{{ residential_address_line_1 }}": 1,
        "{{ residential_address_line_2 }}": 1,
        "{{ service_address_line_1 }}": 1,
        "{{ service_address_line_2 }}": 1,
        "{{ business_occupation }}": 1,
        "{{ email }}": 1,
        "{{ phone }}": 1,
    }
)

NOTICE_MARKERS = Counter(
    {
        "{{ company_name }}": 2,
        "{{ director_name }}": 3,
        "{{ director_identification }}": 1,
        "{{ date_of_birth }}": 1,
        "{{ nationality_and_race }}": 1,
        "{{ residential_address_line_1 }}": 1,
        "{{ residential_address_line_2 }}": 1,
        "{{ residential_address_line_3 }}": 1,
        "{{ service_address }}": 1,
        "{{ business_occupation }}": 1,
        "{{ email }}": 1,
        "{{ shares_fully_owned }}": 1,
    }
)

LEGACY_SAMPLE_TEXT = (
    "2024B068109",
    "{ company name }",
    "HOSAY 3 BAKERY SDN. BHD.",
    "TAN HUI KEE",
    "930412-02-5193",
    "8 December 2024",
    "12 APRIL 1993",
    "MALAYSIAN/CHINESE",
    "51 Lorong Berlian Indah 3",
    "51 LORONG BERLIAN INDAH 3",
    "11 Jalan Seruling",
    "11 JALAN SERULING",
    "ahqiitan1204@gmail.com",
    "017-5962284",
    "(director)",
    "(director ic)",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _node_text(node) -> str:
    return node.text or ""


def _set_text(node, value: str) -> None:
    node.text = value
    key = f"{{{XML_NS}}}space"
    if value[:1].isspace() or value[-1:].isspace():
        node.set(key, "preserve")
    else:
        node.attrib.pop(key, None)


def _replace_once(nodes: list, old: str, new: str) -> bool:
    combined = "".join(_node_text(node) for node in nodes)
    start = combined.find(old)
    if start < 0:
        return False
    end = start + len(old)
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for node in nodes:
        next_cursor = cursor + len(_node_text(node))
        offsets.append((cursor, next_cursor))
        cursor = next_cursor
    first = next(i for i, (_, stop) in enumerate(offsets) if start < stop)
    last = next(i for i, (_, stop) in enumerate(offsets) if end <= stop)
    prefix = _node_text(nodes[first])[: start - offsets[first][0]]
    suffix = _node_text(nodes[last])[end - offsets[last][0] :]
    if first == last:
        _set_text(nodes[first], prefix + new + suffix)
    else:
        _set_text(nodes[first], prefix + new)
        for index in range(first + 1, last):
            _set_text(nodes[index], "")
        _set_text(nodes[last], suffix)
    return True


def _replace_in_paragraphs(root, old: str, new: str, expected: int) -> None:
    count = 0
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        nodes = paragraph.xpath(".//w:t", namespaces=NS)
        while nodes and _replace_once(nodes, old, new):
            count += 1
    if count != expected:
        raise ValueError(
            f"Expected {expected} occurrence(s) of {old!r}, found {count}."
        )


def _paragraph_text(paragraph) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))


def _cell_text(cell) -> str:
    return "".join(cell.xpath(".//w:t/text()", namespaces=NS))


def _find_labeled_row(root, label: str):
    wanted = " ".join(label.lower().split())
    matches = []
    for table in root.xpath(".//w:tbl", namespaces=NS):
        rows = table.xpath("./w:tr", namespaces=NS)
        for index, row in enumerate(rows):
            cells = row.xpath("./w:tc", namespaces=NS)
            if any(wanted in " ".join(_cell_text(cell).lower().split()) for cell in cells):
                matches.append((rows, index, cells))
    if len(matches) != 1:
        raise ValueError(f"Expected one row labelled {label!r}, found {len(matches)}.")
    return matches[0]


def _copy_rpr(paragraph):
    run = paragraph.find(f"{W}r")
    if run is None:
        return None
    rpr = run.find(f"{W}rPr")
    return etree.fromstring(etree.tostring(rpr)) if rpr is not None else None


def _set_run_property(rpr, local_name: str, value: str) -> None:
    node = rpr.find(f"{W}{local_name}")
    if node is None:
        node = etree.SubElement(rpr, f"{W}{local_name}")
    node.set(f"{W}val", value)


def _write_marker_paragraph(
    paragraph,
    text: str,
    *,
    black: bool = False,
    font_half_points: int | None = None,
    left_indent_twips: int | None = None,
) -> None:
    rpr = _copy_rpr(paragraph)
    for child in list(paragraph):
        if child.tag != f"{W}pPr":
            paragraph.remove(child)
    if left_indent_twips is not None:
        ppr = paragraph.find(f"{W}pPr")
        if ppr is None:
            ppr = etree.Element(f"{W}pPr")
            paragraph.insert(0, ppr)
        ind = ppr.find(f"{W}ind")
        if ind is None:
            ind = etree.SubElement(ppr, f"{W}ind")
        ind.set(f"{W}left", str(left_indent_twips))
        ind.attrib.pop(f"{W}firstLine", None)
        ind.attrib.pop(f"{W}hanging", None)
    run = etree.SubElement(paragraph, f"{W}r")
    if rpr is None:
        rpr = etree.SubElement(run, f"{W}rPr")
    else:
        run.append(rpr)
    if black:
        _set_run_property(rpr, "color", "000000")
    if font_half_points is not None:
        _set_run_property(rpr, "sz", str(font_half_points))
        _set_run_property(rpr, "szCs", str(font_half_points))
    text_node = etree.SubElement(run, f"{W}t")
    _set_text(text_node, text)


def _write_cell_marker(
    cell,
    text: str,
    *,
    black: bool = False,
    font_half_points: int | None = None,
    left_indent_twips: int | None = None,
) -> None:
    paragraphs = cell.xpath("./w:p", namespaces=NS)
    if not paragraphs:
        paragraphs = [etree.SubElement(cell, f"{W}p")]
    _write_marker_paragraph(
        paragraphs[0],
        text,
        black=black,
        font_half_points=font_half_points,
        left_indent_twips=left_indent_twips,
    )
    for paragraph in paragraphs[1:]:
        _write_marker_paragraph(paragraph, "")


def _set_labeled_value(root, label: str, marker: str) -> None:
    _, _, cells = _find_labeled_row(root, label)
    _write_cell_marker(cells[-1], marker)


def _set_s201_address(root, label: str, line_1: str, line_2: str) -> None:
    rows, index, cells = _find_labeled_row(root, label)
    if index + 1 >= len(rows):
        raise ValueError(f"Continuation row is missing after {label!r}.")
    continuation_cells = rows[index + 1].xpath("./w:tc", namespaces=NS)
    _write_cell_marker(
        cells[-1],
        f": {line_1}",
        black=True,
        font_half_points=24,
    )
    _write_cell_marker(
        continuation_cells[-1],
        line_2,
        black=True,
        font_half_points=24,
        left_indent_twips=180,
    )


def _set_notice_residential_markers(root) -> None:
    _, _, cells = _find_labeled_row(root, "Usual residential address")
    paragraphs = cells[-1].xpath("./w:p", namespaces=NS)
    if len(paragraphs) < 3:
        raise ValueError("Notice residential-address cell requires three paragraphs.")
    for paragraph, marker in zip(
        paragraphs,
        (
            "{{ residential_address_line_1 }}",
            "{{ residential_address_line_2 }}",
            "{{ residential_address_line_3 }}",
        ),
    ):
        _write_marker_paragraph(paragraph, marker, black=True)
    for paragraph in paragraphs[3:]:
        _write_marker_paragraph(paragraph, "")


def _set_notice_share_marker(root) -> None:
    _, _, cells = _find_labeled_row(root, "Amount fully owned by me")
    label_index = next(
        index
        for index, cell in enumerate(cells)
        if "amount fully owned by me" in _cell_text(cell).lower()
    )
    if label_index + 1 >= len(cells):
        raise ValueError("Notice fully-owned-share cell is missing.")
    _write_cell_marker(cells[label_index + 1], "{{ shares_fully_owned }}")


def _marker_counts(root) -> Counter[str]:
    counts: Counter[str] = Counter()
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        text = _paragraph_text(paragraph)
        start = 0
        while True:
            opening = text.find("{{", start)
            if opening < 0:
                break
            closing = text.find("}}", opening + 2)
            if closing < 0:
                break
            marker = text[opening : closing + 2]
            counts[marker] += 1
            start = closing + 2
    return counts


def _assert_marker_inventory(root, expected: Counter[str]) -> None:
    actual = _marker_counts(root)
    if actual != expected:
        raise ValueError(f"Marker inventory mismatch. Expected {expected}; found {actual}.")
    all_text = "\n".join(
        _paragraph_text(paragraph)
        for paragraph in root.xpath(".//w:p", namespaces=NS)
    )
    leaked = [value for value in LEGACY_SAMPLE_TEXT if value in all_text]
    if leaked:
        raise ValueError(f"Legacy sample text remains after conversion: {leaked}")


def _patch_s201(root) -> None:
    _replace_in_paragraphs(
        root,
        "Name: TAN HUI KEE (director)",
        "Name: {{ director_name }}",
        1,
    )
    _replace_in_paragraphs(
        root,
        "Passport No.: 930412-02-5193 (director ic)",
        "{{ identification_label }}: {{ director_id }}",
        1,
    )
    _replace_in_paragraphs(root, "2024B068109", "{{ reference_no }}", 1)
    _replace_in_paragraphs(root, "{ company name }", "{{ company_name }}", 1)
    _replace_in_paragraphs(
        root, "HOSAY 3 BAKERY SDN. BHD.", "{{ company_name }}", 3
    )
    _replace_in_paragraphs(root, "TAN HUI KEE", "{{ director_name }}", 1)
    _replace_in_paragraphs(root, "930412-02-5193", "{{ director_id }}", 1)
    _replace_in_paragraphs(
        root,
        "Date of Declaration:  8 December 2024",
        "Date of Declaration: {{ declaration_date }}",
        1,
    )
    _replace_in_paragraphs(root, "8 December 2024", "{{ declaration_date }}", 1)
    _replace_in_paragraphs(
        root, "NRIC / Passport No.", "{{ identification_label }}", 1
    )
    _set_s201_address(
        root,
        "Residential Address",
        "{{ residential_address_line_1 }}",
        "{{ residential_address_line_2 }}",
    )
    _set_s201_address(
        root,
        "Service Address",
        "{{ service_address_line_1 }}",
        "{{ service_address_line_2 }}",
    )
    _set_labeled_value(root, "Business Occupation", ": {{ business_occupation }}")
    _set_labeled_value(root, "E-Mail Address", ": {{ email }}")
    _set_labeled_value(root, "Telephone No.", ": {{ phone }}")
    _assert_marker_inventory(root, S201_MARKERS)


def _normalize_converted_s201(root) -> None:
    old = "Date of Declaration:  {{ declaration_date }}"
    new = "Date of Declaration: {{ declaration_date }}"
    old_count = sum(
        _paragraph_text(paragraph).count(old)
        for paragraph in root.xpath(".//w:p", namespaces=NS)
    )
    new_count = sum(
        _paragraph_text(paragraph).count(new)
        for paragraph in root.xpath(".//w:p", namespaces=NS)
    )
    if old_count == 1:
        _replace_in_paragraphs(root, old, new, 1)
    elif old_count != 0 or new_count != 1:
        raise ValueError("S201 declaration-date signature marker is ambiguous.")
    _assert_marker_inventory(root, S201_MARKERS)


def _patch_notice(root) -> None:
    _replace_in_paragraphs(
        root, "HOSAY 3 BAKERY SDN. BHD.", "{{ company_name }}", 2
    )
    _replace_in_paragraphs(root, "TAN HUI KEE", "{{ director_name }}", 3)
    _replace_in_paragraphs(
        root, "930412-02-5193", "{{ director_identification }}", 1
    )
    _replace_in_paragraphs(root, "12 APRIL 1993", "{{ date_of_birth }}", 1)
    _replace_in_paragraphs(
        root, "MALAYSIAN/CHINESE", "{{ nationality_and_race }}", 1
    )
    _set_notice_residential_markers(root)
    _set_labeled_value(root, "Service address", "{{ service_address }}")
    _set_labeled_value(root, "E-Mail Address", "{{ email }}")
    _set_labeled_value(root, "Business occupation", "{{ business_occupation }}")
    _set_notice_share_marker(root)
    _assert_marker_inventory(root, NOTICE_MARKERS)


def _write_patched(template_path: Path, patcher) -> None:
    temporary_path = template_path.with_suffix(".marker-conversion.tmp.docx")
    try:
        with ZipFile(template_path, "r") as source:
            root = etree.fromstring(source.read("word/document.xml"))
            patcher(root)
            patched_xml = etree.tostring(
                root,
                xml_declaration=True,
                encoding="UTF-8",
                standalone=True,
            )
            with ZipFile(temporary_path, "w", compression=ZIP_DEFLATED) as target:
                for info in source.infolist():
                    payload = (
                        patched_xml
                        if info.filename == "word/document.xml"
                        else source.read(info.filename)
                    )
                    target.writestr(info, payload)
        os.replace(temporary_path, template_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _preserve_original(template_path: Path) -> Path:
    expected_hash = ORIGINAL_HASHES[template_path.name]
    actual_hash = _sha256(template_path)
    backup_path = BACKUP_DIR / template_path.name
    if backup_path.exists():
        if _sha256(backup_path) != expected_hash:
            raise ValueError(f"Original-template backup hash mismatch: {backup_path}")
        return backup_path
    if actual_hash != expected_hash:
        raise ValueError(
            f"Refusing to back up an unexpected template version: {template_path}"
        )
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, backup_path)
    return backup_path


def convert_templates() -> None:
    jobs = (
        (
            TEMPLATE_DIR / S201_FILENAME,
            _patch_s201,
            _normalize_converted_s201,
            S201_MARKERS,
        ),
        (TEMPLATE_DIR / NOTICE_FILENAME, _patch_notice, None, NOTICE_MARKERS),
    )
    for template_path, patcher, normalizer, expected_markers in jobs:
        _preserve_original(template_path)
        with ZipFile(template_path, "r") as package:
            root = etree.fromstring(package.read("word/document.xml"))
        if _marker_counts(root) == expected_markers:
            _assert_marker_inventory(root, expected_markers)
            if normalizer is not None:
                _write_patched(template_path, normalizer)
            continue
        _write_patched(template_path, patcher)


if __name__ == "__main__":
    convert_templates()
