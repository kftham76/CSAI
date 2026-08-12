from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from .convert_templates_to_markers import (
    BACKUP_DIR,
    LEGACY_SAMPLE_TEXT,
    NOTICE_FILENAME,
    NOTICE_MARKERS,
    ORIGINAL_HASHES,
    S201_FILENAME,
    S201_MARKERS,
    TEMPLATE_DIR,
)
from .renderer import NOTICE_TEMPLATE_MARKERS, S201_TEMPLATE_MARKERS, TOKEN_PATTERN


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
W = f"{{{W_NS}}}"
NEW_TEMPLATE_HASHES = {
    S201_FILENAME: "6b73455b1de211c804c8ffa27158f24cdf51658ffca7fd654a8c005307f086f7",
    NOTICE_FILENAME: "51a500c96c451e5a12ed4cd5cf869c212ccb86bbc8f25b5cc17f73c34f7ec688",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _root(path: Path):
    with ZipFile(path) as package:
        return etree.fromstring(package.read("word/document.xml"))


def _paragraph_text(paragraph) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))


def _marker_counts(root) -> Counter[str]:
    counts: Counter[str] = Counter()
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        counts.update(TOKEN_PATTERN.findall(_paragraph_text(paragraph)))
    return counts


def _canonical_nodes(root, xpath: str) -> list[bytes]:
    return [
        etree.tostring(node, method="c14n", exclusive=True)
        for node in root.xpath(xpath, namespaces=NS)
    ]


def _assert_non_document_parts_match(template: Path, backup: Path) -> None:
    with ZipFile(template) as converted, ZipFile(backup) as original:
        assert converted.namelist() == original.namelist()
        for name in original.namelist():
            if name != "word/document.xml":
                assert converted.read(name) == original.read(name), name


def _assert_document_invariants(converted_root, original_root) -> None:
    for xpath in (
        ".//w:sectPr",
        ".//w:tblPr",
        ".//w:tblGrid",
        ".//w:trPr",
        ".//w:tcPr",
    ):
        assert _canonical_nodes(converted_root, xpath) == _canonical_nodes(
            original_root, xpath
        ), xpath


def _assert_address_run(root, marker: str, *, continuation: bool) -> None:
    matches = []
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        if marker in _paragraph_text(paragraph):
            matches.append(paragraph)
    assert len(matches) == 1, marker
    paragraph = matches[0]
    text_nodes = [
        node
        for node in paragraph.xpath(".//w:t", namespaces=NS)
        if marker in (node.text or "")
    ]
    assert len(text_nodes) == 1, marker
    rpr = text_nodes[0].getparent().find(f"{W}rPr")
    assert rpr is not None, marker
    color = rpr.find(f"{W}color")
    size = rpr.find(f"{W}sz")
    assert color is not None and color.get(f"{W}val") == "000000", marker
    assert size is not None and size.get(f"{W}val") == "24", marker
    ind = paragraph.find(f"{W}pPr/{W}ind")
    if continuation:
        assert ind is not None and ind.get(f"{W}left") == "180", marker


def audit_templates() -> dict[str, object]:
    results: dict[str, object] = {}
    jobs = (
        (S201_FILENAME, S201_MARKERS, S201_TEMPLATE_MARKERS),
        (NOTICE_FILENAME, NOTICE_MARKERS, NOTICE_TEMPLATE_MARKERS),
    )
    for filename, expected, renderer_expected in jobs:
        template = TEMPLATE_DIR / filename
        backup = BACKUP_DIR / filename
        assert _sha256(backup) == ORIGINAL_HASHES[filename]
        assert _sha256(template) == NEW_TEMPLATE_HASHES[filename]
        assert expected == renderer_expected
        converted_root = _root(template)
        original_root = _root(backup)
        actual_markers = _marker_counts(converted_root)
        assert actual_markers == expected, (filename, actual_markers)
        all_text = "\n".join(
            _paragraph_text(paragraph)
            for paragraph in converted_root.xpath(".//w:p", namespaces=NS)
        )
        assert not [value for value in LEGACY_SAMPLE_TEXT if value in all_text]
        _assert_non_document_parts_match(template, backup)
        _assert_document_invariants(converted_root, original_root)
        results[filename] = {
            "original_sha256": ORIGINAL_HASHES[filename],
            "converted_sha256": NEW_TEMPLATE_HASHES[filename],
            "marker_counts": dict(sorted(actual_markers.items())),
            "non_document_parts_unchanged": True,
            "section_table_cell_geometry_unchanged": True,
            "legacy_sample_text_absent": True,
            "renderer_marker_contract_matches": True,
        }
    s201_root = _root(TEMPLATE_DIR / S201_FILENAME)
    for marker in (
        "{{ residential_address_line_1 }}",
        "{{ service_address_line_1 }}",
    ):
        _assert_address_run(s201_root, marker, continuation=False)
    for marker in (
        "{{ residential_address_line_2 }}",
        "{{ service_address_line_2 }}",
    ):
        _assert_address_run(s201_root, marker, continuation=True)
    results["s201_address_format"] = {
        "marker_color": "000000",
        "template_font_size_pt": 12,
        "continuation_indent_twips": 180,
    }
    return results


if __name__ == "__main__":
    print(json.dumps(audit_templates(), indent=2, sort_keys=True))
