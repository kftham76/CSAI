from __future__ import annotations

import re
import textwrap
from collections import Counter
from decimal import Decimal
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree

from .models import DirectorContext, PreIncorpContext
from .value_utils import identification_type_code


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W_NS}
W = f"{{{W_NS}}}"
TOKEN_PATTERN = re.compile(r"\{\{\s*[^{}]+?\s*\}\}")

S201_TEMPLATE_MARKERS = Counter(
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

NOTICE_TEMPLATE_MARKERS = Counter(
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

S201_ADDRESS_NORMAL_CAPACITY = 44
S201_ADDRESS_COMPACT_CAPACITY = 60
S201_ADDRESS_NORMAL_HALF_POINTS = 24
S201_ADDRESS_COMPACT_HALF_POINTS = 21


def format_date(value, *, uppercase: bool = False) -> str:
    text = f"{value.day} {value.strftime('%B')} {value.year}"
    return text.upper() if uppercase else text


def format_shares(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


def format_nationality(value: str) -> str:
    normalized = value.strip().upper()
    return "MALAYSIAN" if normalized == "MALAYSIA" else normalized


def format_identification(id_number: str, id_type: str) -> str:
    code = identification_type_code(id_type)
    if not code:
        raise ValueError(f"Unsupported identification type: {id_type}")
    return f"{id_number} ({code})"


def format_identification_label(id_type: str) -> str:
    code = identification_type_code(id_type)
    labels = {
        "B": "NRIC No.",
        "P": "Passport No.",
        "R": "Red IC No.",
        "Z": "Military ID No.",
        "M": "Police ID No.",
    }
    if not code or code not in labels:
        raise ValueError(f"Unsupported identification type: {id_type}")
    return labels[code]


def _node_text(node) -> str:
    return node.text or ""


def _set_text(node, value: str) -> None:
    node.text = value
    key = f"{{{XML_NS}}}space"
    if value[:1].isspace() or value[-1:].isspace():
        node.set(key, "preserve")
    else:
        node.attrib.pop(key, None)


def _replace_token(nodes: list, token: str, replacement: str) -> bool:
    """Replace one run-spanning token while preserving the surrounding runs."""
    combined = "".join(_node_text(node) for node in nodes)
    start = combined.find(token)
    if start < 0:
        return False
    end = start + len(token)
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
        _set_text(nodes[first], prefix + replacement + suffix)
    else:
        _set_text(nodes[first], prefix + replacement)
        for index in range(first + 1, last):
            _set_text(nodes[index], "")
        _set_text(nodes[last], suffix)
    return True


def _paragraph_text(paragraph) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))


def _marker_counts(root) -> Counter[str]:
    counts: Counter[str] = Counter()
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        counts.update(TOKEN_PATTERN.findall(_paragraph_text(paragraph)))
    return counts


def _validate_template_markers(root, expected: Counter[str]) -> None:
    actual = _marker_counts(root)
    if actual != expected:
        missing = expected - actual
        unexpected = actual - expected
        raise ValueError(
            "Template marker inventory is invalid. "
            f"Missing or duplicated markers: {dict(missing)}; "
            f"unexpected markers: {dict(unexpected)}."
        )


def _replace_marker(root, token: str, replacement: str, expected: int) -> None:
    count = 0
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        nodes = paragraph.xpath(".//w:t", namespaces=NS)
        while nodes and _replace_token(nodes, token, replacement):
            count += 1
    if count != expected:
        raise ValueError(
            f"Expected {expected} occurrence(s) of marker {token!r}, found {count}."
        )


def _replace_marker_map(root, replacements: dict[str, str], expected: Counter[str]) -> None:
    if set(replacements) != set(expected):
        missing = set(expected) - set(replacements)
        extra = set(replacements) - set(expected)
        raise ValueError(
            f"Renderer marker-map mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    _validate_template_markers(root, expected)
    for marker, value in replacements.items():
        _replace_marker(root, marker, value, expected[marker])
    unresolved = _marker_counts(root)
    if unresolved:
        raise ValueError(f"Unresolved template markers remain: {dict(unresolved)}")


def _set_run_property(run, local_name: str, value: str) -> None:
    rpr = run.find(f"{W}rPr")
    if rpr is None:
        rpr = etree.Element(f"{W}rPr")
        run.insert(0, rpr)
    node = rpr.find(f"{W}{local_name}")
    if node is None:
        node = etree.SubElement(rpr, f"{W}{local_name}")
    node.set(f"{W}val", value)


def _format_marker_runs(root, markers: tuple[str, ...], half_points: int) -> None:
    for marker in markers:
        matches = []
        for paragraph in root.xpath(".//w:p", namespaces=NS):
            if marker not in _paragraph_text(paragraph):
                continue
            for text_node in paragraph.xpath(".//w:t", namespaces=NS):
                if marker in _node_text(text_node):
                    matches.append(text_node)
        if len(matches) != 1:
            raise ValueError(
                f"Address marker {marker!r} must occupy exactly one run; found {len(matches)}."
            )
        run = matches[0].getparent()
        _set_run_property(run, "color", "000000")
        _set_run_property(run, "sz", str(half_points))
        _set_run_property(run, "szCs", str(half_points))


def _balanced_two_lines(address: str) -> tuple[tuple[str, str], bool]:
    normalized = re.sub(r"\s+", " ", address).strip()
    if not normalized:
        raise ValueError("Address cannot be blank.")
    words = normalized.split(" ")
    if any(len(word) > S201_ADDRESS_COMPACT_CAPACITY for word in words):
        raise ValueError(
            "Address contains a word that cannot fit within the two-line S201 field."
        )
    if len(words) == 1:
        candidates = [(words[0], "")]
    else:
        candidates = [
            (" ".join(words[:index]), " ".join(words[index:]))
            for index in range(1, len(words))
        ]
    fitting = [
        lines
        for lines in candidates
        if max(len(lines[0]), len(lines[1])) <= S201_ADDRESS_COMPACT_CAPACITY
    ]
    if not fitting:
        raise ValueError(
            "Address cannot fit in two S201 lines at the compact 10.5 pt size."
        )
    lines = min(
        fitting,
        key=lambda value: (
            max(len(value[0]), len(value[1])),
            abs(len(value[0]) - len(value[1])),
        ),
    )
    compact = max(len(lines[0]), len(lines[1])) > S201_ADDRESS_NORMAL_CAPACITY
    return lines, compact


def _wrap(value: str, width: int, maximum: int) -> list[str]:
    lines = textwrap.wrap(
        re.sub(r"\s+", " ", value).strip(),
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]
    if len(lines) > maximum:
        lines = lines[: maximum - 1] + [" ".join(lines[maximum - 1 :])]
    return lines + [""] * (maximum - len(lines))


def _patch_package(template_path: Path, output_path: Path, patcher) -> Path:
    with ZipFile(template_path, "r") as source:
        root = etree.fromstring(source.read("word/document.xml"))
        patcher(root)
        patched_xml = etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as target:
            for info in source.infolist():
                payload = (
                    patched_xml
                    if info.filename == "word/document.xml"
                    else source.read(info.filename)
                )
                target.writestr(info, payload)
    return output_path


def render_s201(
    template_path: Path,
    output_path: Path,
    context: PreIncorpContext,
    director: DirectorContext,
    reference_no: str,
) -> Path:
    def patch(root) -> None:
        residential_lines, residential_compact = _balanced_two_lines(
            director.residential_address
        )
        service_lines, service_compact = _balanced_two_lines(director.service_address)
        _format_marker_runs(
            root,
            (
                "{{ residential_address_line_1 }}",
                "{{ residential_address_line_2 }}",
            ),
            (
                S201_ADDRESS_COMPACT_HALF_POINTS
                if residential_compact
                else S201_ADDRESS_NORMAL_HALF_POINTS
            ),
        )
        _format_marker_runs(
            root,
            (
                "{{ service_address_line_1 }}",
                "{{ service_address_line_2 }}",
            ),
            (
                S201_ADDRESS_COMPACT_HALF_POINTS
                if service_compact
                else S201_ADDRESS_NORMAL_HALF_POINTS
            ),
        )
        replacements = {
            "{{ reference_no }}": reference_no,
            "{{ company_name }}": context.company_name,
            "{{ director_name }}": director.name,
            "{{ identification_label }}": format_identification_label(director.id_type),
            "{{ director_id }}": director.id_number,
            "{{ declaration_date }}": format_date(context.declaration_date),
            "{{ residential_address_line_1 }}": residential_lines[0],
            "{{ residential_address_line_2 }}": residential_lines[1],
            "{{ service_address_line_1 }}": service_lines[0],
            "{{ service_address_line_2 }}": service_lines[1],
            "{{ business_occupation }}": director.occupation,
            "{{ email }}": director.email,
            "{{ phone }}": director.phone,
        }
        _replace_marker_map(root, replacements, S201_TEMPLATE_MARKERS)

    return _patch_package(template_path, output_path, patch)


def render_notice(
    template_path: Path,
    output_path: Path,
    context: PreIncorpContext,
    director: DirectorContext,
) -> Path:
    def patch(root) -> None:
        identification = format_identification(director.id_number, director.id_type)
        residential = _wrap(director.residential_address.upper(), 40, 3)
        replacements = {
            "{{ company_name }}": context.company_name,
            "{{ director_name }}": director.name,
            "{{ director_identification }}": identification,
            "{{ date_of_birth }}": format_date(director.date_of_birth, uppercase=True),
            "{{ nationality_and_race }}": (
                f"{format_nationality(director.nationality)}/{director.race.upper()}"
            ),
            "{{ residential_address_line_1 }}": residential[0],
            "{{ residential_address_line_2 }}": residential[1],
            "{{ residential_address_line_3 }}": residential[2],
            "{{ service_address }}": director.service_address.upper(),
            "{{ business_occupation }}": director.occupation.upper(),
            "{{ email }}": director.email,
            "{{ shares_fully_owned }}": format_shares(director.shares),
        }
        _replace_marker_map(root, replacements, NOTICE_TEMPLATE_MARKERS)

    return _patch_package(template_path, output_path, patch)
