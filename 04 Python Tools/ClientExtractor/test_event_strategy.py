import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("extract_client_final.py")
SPEC = importlib.util.spec_from_file_location("extract_client_final", MODULE_PATH)
extractor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = extractor
SPEC.loader.exec_module(extractor)


def filing(
    folder,
    section,
    effective_date,
    *,
    name="TEST COMPANY SDN. BHD.",
    registration="202001000001",
    members=None,
    directors=None,
    events=None,
    total=None,
    path=None,
    filing_ref="",
    quality=2,
    status="VALID",
    sha256="",
    lodgement_date=None,
    lodgement_source="",
):
    return extractor.FilingRecord(
        path=path or str(folder / f"{section}-{effective_date:%Y%m%d}.pdf"),
        folder=folder.name,
        size=100,
        mtime_ns=1,
        sha256=sha256,
        section=section,
        status=status,
        quality=quality,
        registration_no=registration,
        filing_ref=filing_ref,
        effective_date=effective_date,
        lodgement_date=lodgement_date,
        lodgement_date_source=lodgement_source,
        company_name=name if section in {"S14", "S68"} else "",
        total_shares=total,
        members=members or [],
        directors=directors or [],
        officer_events=events or [],
    )


def member(name, identifier, shares):
    return {
        "Type": "INDIVIDUAL",
        "Name": name,
        "ID Type": "MYKAD",
        "ID No": identifier,
        "Nationality": "MALAYSIA",
        "Race": "CHINESE",
        "Gender": "",
        "DOB": "",
        "Address": "",
        "Shares": shares,
        "Share Type": "ORDINARY SHARES",
        "Analysis": "",
    }


def director(name, identifier):
    return {
        "Name": name,
        "IC": identifier,
        "DOB": "",
        "Nationality": "MALAYSIA",
        "Race": "",
        "Gender": "",
        "Residential": "",
        "Service Address": "",
    }


class EventStrategyTests(unittest.TestCase):
    def test_lodgement_date_sources_and_reference_prefixes(self):
        for prefix in ("ROM", "CPO", "ROA", "XBAR"):
            with self.subTest(prefix=prefix):
                date, source = extractor.extract_lodgement_date(
                    f"Lodging Reference Number: {prefix}2006202500207"
                )
                self.assertEqual(date, datetime(2025, 6, 20))
                self.assertEqual(source, "REFERENCE")

        explicit, source = extractor.extract_lodgement_date(
            "Date of Lodgement: 21/06/2025"
        )
        self.assertEqual(explicit, datetime(2025, 6, 21))
        self.assertEqual(source, "DOCUMENT")

        filename, source = extractor.extract_lodgement_date(
            "",
            Path("Section 58 dated 27 July 2022.pdf"),
        )
        self.assertEqual(filename, datetime(2022, 7, 27))
        self.assertEqual(source, "FILENAME")

    def test_annual_return_date_is_not_a_lodgement_date(self):
        text = "Date of annual return 2025-07-27"
        self.assertEqual(extractor.extract_submission_date(text), "")
        self.assertEqual(extractor.extract_lodgement_date(text), (None, ""))

    def test_master_date_columns_are_adjacent_and_use_latest_valid_filings(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            annual_return = filing(
                folder,
                "S68",
                datetime(2025, 7, 27),
                lodgement_date=datetime(2025, 8, 17),
            )
            section51 = filing(
                folder,
                "S51",
                datetime(2025, 6, 19),
                lodgement_date=datetime(2025, 6, 20),
            )
            section58 = filing(
                folder,
                "S58",
                datetime(2023, 6, 9),
                lodgement_date=datetime(2023, 6, 15),
            )
            section78 = filing(
                folder,
                "S78",
                datetime(2025, 6, 19),
                lodgement_date=datetime(2025, 6, 19),
            )
            ignored = filing(
                folder,
                "S51",
                datetime(2026, 1, 1),
                lodgement_date=datetime(2026, 1, 2),
                status="EXCLUDED",
            )
            records = [
                annual_return, section51, section58, section78, ignored,
            ]
            row, _, _ = extractor.resolve_company_event_aware(folder, records)
            columns = list(row)
            start = columns.index("Annual Return Date")
            self.assertEqual(
                columns[start:start + 5],
                [
                    "Annual Return Date",
                    "Date of Lodgement (AR)",
                    "Section 51 Date",
                    "Section 58 Date",
                    "Section 78 Date",
                ],
            )
            self.assertEqual(
                [row[column] for column in columns[start:start + 5]],
                [
                    "27/07/2025",
                    "17/08/2025",
                    "20/06/2025",
                    "15/06/2023",
                    "19/06/2025",
                ],
            )

    def test_scan_reextracts_instead_of_using_persisted_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            pdf = folder / "Section 51.pdf"
            pdf.write_bytes(b"not a real PDF")
            rebuilt = filing(folder, "S51", datetime(2025, 1, 1), path=str(pdf))
            with patch.object(
                extractor,
                "build_filing_record",
                return_value=rebuilt,
            ) as build:
                records = extractor.scan_company_filings(
                    folder,
                    cache={str(pdf): {"ParsedJSON": "stale"}},
                )
            self.assertEqual(records, [rebuilt])
            build.assert_called_once()

    def test_incorporation_ocr_prefers_section17_and_stops_early(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            combined = folder / "section 14 15 17 58.pdf"
            certificate = folder / "section 17.pdf"
            combined.write_bytes(b"combined")
            certificate.write_bytes(b"certificate")
            ocr_text = (
                "CERTIFICATE OF INCORPORATION on and from the "
                "27th day of July 2020, incorporated under the Companies Act"
            )
            with (
                patch.object(extractor, "read_pdf", return_value=""),
                patch.object(
                    extractor,
                    "try_ocr_pdf",
                    return_value=ocr_text,
                ) as ocr,
            ):
                value = extractor.find_incorporation_date_in_folder(folder)
            self.assertEqual(value, "27/07/2020")
            self.assertEqual(Path(ocr.call_args.args[0]).name, "section 17.pdf")
            self.assertTrue(callable(ocr.call_args.kwargs["stop_when"]))

    def test_unreachable_legacy_main_block_was_removed(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn('if False and __name__ == "__main__":', source)
        self.assertEqual(source.count('if __name__ == "__main__":'), 1)

    def test_content_classifier_does_not_confuse_section_513(self):
        false_text = (
            "COMPANIES ACT 2016 SECTION 513 "
            "NOTICE OF APPOINTMENT AND ADDRESS OF LIQUIDATOR"
        )
        true_text = (
            "COMPANIES ACT 2016 SECTION 51 REGISTER OF MEMBER"
        )
        self.assertEqual(extractor.classify_statutory_text(false_text), "OTHER")
        self.assertEqual(extractor.classify_statutory_text(true_text), "S51")
        self.assertEqual(
            extractor.infer_section_from_path(
                Path("NOTICE Section 513(1) Lodged.pdf")
            ),
            "",
        )

    def test_duplicate_hash_and_filing_reference_are_applied_once(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            first = filing(
                folder,
                "S51",
                datetime(2025, 9, 25),
                filing_ref="ROM2509202500092",
                sha256="same",
                path=str(folder / "Form" / "one.pdf"),
            )
            duplicate = filing(
                folder,
                "S51",
                datetime(2025, 9, 25),
                filing_ref="ROM2509202500092",
                sha256="same",
                path=str(folder / "Transfer" / "two.pdf"),
            )
            canonical, issues = extractor.canonicalize_filings(
                [first, duplicate]
            )
            self.assertEqual(len(canonical), 1)
            self.assertEqual(
                {first.status, duplicate.status},
                {"VALID", "DUPLICATE"},
            )
            self.assertEqual(issues, [])

    def test_approved_source_wins_same_filing_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            approved = filing(
                folder,
                "S68",
                datetime(2025, 8, 2),
                filing_ref="XBAR1",
                quality=3,
                sha256="approved",
                path=str(folder / "AR Approval.pdf"),
            )
            draft = filing(
                folder,
                "S68",
                datetime(2025, 8, 2),
                filing_ref="XBAR1",
                quality=2,
                sha256="draft",
                path=str(folder / "AR Draft.pdf"),
            )
            canonical, issues = extractor.canonicalize_filings(
                [draft, approved]
            )
            self.assertEqual(canonical, [approved])
            self.assertEqual(draft.status, "DUPLICATE")
            self.assertEqual(issues[0]["Code"], "FILING_REFERENCE_CONFLICT")

    def test_section78_after_snapshot_is_additive(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            annual_return = filing(
                folder,
                "S68",
                datetime(2025, 1, 1),
                members=[member("ALICE", "800101010101", 100)],
                directors=[director("ALICE", "800101010101")],
                total=100,
            )
            allotment_member = member("BOB", "810101010101", 50)
            allotment_member["Allotted Shares"] = 50
            allotment = filing(
                folder,
                "S78",
                datetime(2025, 2, 1),
                members=[allotment_member],
                total=150,
            )
            records = [annual_return, allotment]
            extractor.canonicalize_filings(records)
            row, _, issues = extractor.resolve_company_event_aware(
                folder, records
            )
            self.assertEqual(row["Total Issued Shares"], 150)
            self.assertEqual(
                [(item["Name"], item["Shares"]) for item in row["_members"]],
                [("ALICE", 100), ("BOB", 50)],
            )
            self.assertFalse(
                [item for item in issues if item["Severity"] == "CRITICAL"]
            )

    def test_later_section51_absorbs_earlier_allotment(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            annual_return = filing(
                folder,
                "S68",
                datetime(2025, 1, 1),
                members=[member("ALICE", "800101010101", 100)],
                total=100,
            )
            allotment_member = member("BOB", "810101010101", 50)
            allotment_member["Allotted Shares"] = 50
            allotment = filing(
                folder,
                "S78",
                datetime(2025, 2, 1),
                members=[allotment_member],
                total=150,
            )
            section51_members = [
                {
                    "Type": "INDIVIDUAL",
                    "Name": "ALICE",
                    "IC": "800101010101",
                    "Shares": 100,
                    "Transferred In": 0,
                    "Transferred Out": 0,
                    "Date": "01/03/2025",
                },
                {
                    "Type": "INDIVIDUAL",
                    "Name": "BOB",
                    "IC": "810101010101",
                    "Shares": 50,
                    "Transferred In": 50,
                    "Transferred Out": 0,
                    "Date": "01/03/2025",
                },
            ]
            section51 = filing(
                folder,
                "S51",
                datetime(2025, 3, 1),
                members=section51_members,
                total=150,
            )
            records = [annual_return, allotment, section51]
            extractor.canonicalize_filings(records)
            row, _, _ = extractor.resolve_company_event_aware(folder, records)
            self.assertEqual(row["Total Issued Shares"], 150)
            self.assertEqual(
                {item["Name"]: item["Shares"] for item in row["_members"]},
                {"ALICE": 100, "BOB": 50},
            )

    def test_middle_director_event_recomputes_downstream_state(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            annual_return = filing(
                folder,
                "S68",
                datetime(2025, 1, 1),
                members=[member("ALICE", "800101010101", 100)],
                directors=[director("ALICE", "800101010101")],
                total=100,
            )
            appoint_bob = filing(
                folder,
                "S58",
                datetime(2025, 3, 1),
                events=[{
                    **director("BOB", "810101010101"),
                    "Event Type": "APPOINT",
                    "Event Date": "01/03/2025",
                    "Appointment Date": "01/03/2025",
                }],
            )
            records = [annual_return, appoint_bob]
            extractor.canonicalize_filings(records)
            before, _, _ = extractor.resolve_company_event_aware(
                folder, records
            )
            cease_alice = filing(
                folder,
                "S58",
                datetime(2025, 2, 1),
                events=[{
                    **director("ALICE", "800101010101"),
                    "Event Type": "CEASE",
                    "Event Date": "01/02/2025",
                }],
            )
            records.insert(1, cease_alice)
            extractor.canonicalize_filings(records)
            after, _, _ = extractor.resolve_company_event_aware(
                folder, records
            )
            self.assertEqual(
                [
                    value
                    for key, value in before.items()
                    if key.startswith("Director") and key.endswith(" Name")
                ],
                ["ALICE", "BOB"],
            )
            self.assertEqual(
                [
                    value
                    for key, value in after.items()
                    if key.startswith("Director") and key.endswith(" Name")
                ],
                ["BOB"],
            )

    def test_invalid_new_snapshot_retains_last_validated_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            annual_return = filing(
                folder,
                "S68",
                datetime(2025, 1, 1),
                members=[member("ALICE", "800101010101", 100)],
                total=100,
            )
            invalid_section51 = filing(
                folder,
                "S51",
                datetime(2025, 2, 1),
                members=[{
                    "Name": "BOB",
                    "IC": "810101010101",
                    "Shares": 50,
                    "Date": "01/02/2025",
                }],
                total=100,
            )
            records = [annual_return, invalid_section51]
            extractor.canonicalize_filings(records)
            row, _, issues = extractor.resolve_company_event_aware(
                folder, records
            )
            self.assertEqual(
                [(item["Name"], item["Shares"]) for item in row["_members"]],
                [("ALICE", 100)],
            )
            self.assertIn(
                "INVALID_MEMBER_SNAPSHOT",
                {item["Code"] for item in issues},
            )

    def test_registration_mismatch_is_quarantined(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            annual_return = filing(
                folder,
                "S68",
                datetime(2025, 1, 1),
                members=[member("ALICE", "800101010101", 100)],
                total=100,
            )
            foreign_filing = filing(
                folder,
                "S78",
                datetime(2025, 2, 1),
                registration="202099999999",
                members=[{
                    **member("BOB", "810101010101", 50),
                    "Allotted Shares": 50,
                }],
                total=150,
            )
            records = [annual_return, foreign_filing]
            canonical, issues = extractor.canonicalize_filings(records)
            self.assertEqual(canonical, [annual_return])
            self.assertEqual(foreign_filing.status, "REG_MISMATCH")
            self.assertIn(
                "REGISTRATION_NUMBER_MISMATCH",
                {item["Code"] for item in issues},
            )

    def test_new_and_legacy_registration_numbers_are_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            old_annual_return = filing(
                folder,
                "S68",
                datetime(2024, 1, 1),
                registration="1057121-X",
                members=[member("ALICE", "800101010101", 100)],
                total=100,
                sha256="old",
            )
            new_annual_return = filing(
                folder,
                "S68",
                datetime(2025, 1, 1),
                registration="201301027293 (1057121-X)",
                members=[member("ALICE", "800101010101", 100)],
                total=100,
                sha256="new",
            )
            records = [old_annual_return, new_annual_return]
            canonical, issues = extractor.canonicalize_filings(records)
            self.assertEqual(canonical, records)
            self.assertEqual(
                {record.status for record in records},
                {"VALID"},
            )
            self.assertNotIn(
                "REGISTRATION_NUMBER_MISMATCH",
                {item["Code"] for item in issues},
            )

    def test_same_date_conflicting_director_events_are_not_applied(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            annual_return = filing(
                folder,
                "S68",
                datetime(2025, 1, 1),
                members=[member("ALICE", "800101010101", 100)],
                directors=[director("ALICE", "800101010101")],
                total=100,
            )
            conflict = filing(
                folder,
                "S58",
                datetime(2025, 2, 1),
                events=[
                    {
                        **director("ALICE", "800101010101"),
                        "Event Type": "CEASE",
                        "Event Date": "01/02/2025",
                    },
                    {
                        **director("ALICE", "800101010101"),
                        "Event Type": "APPOINT",
                        "Event Date": "01/02/2025",
                        "Appointment Date": "01/02/2025",
                    },
                ],
            )
            records = [annual_return, conflict]
            extractor.canonicalize_filings(records)
            row, _, issues = extractor.resolve_company_event_aware(
                folder, records
            )
            self.assertEqual(row["Director1 Name"], "ALICE")
            self.assertIn(
                "SAME_DATE_DIRECTOR_CONFLICT",
                {item["Code"] for item in issues},
            )

    def test_same_date_conflicting_member_snapshots_keep_earlier_state(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            annual_return = filing(
                folder,
                "S68",
                datetime(2025, 1, 1),
                members=[member("ALICE", "800101010101", 100)],
                total=100,
            )
            first = filing(
                folder,
                "S51",
                datetime(2025, 2, 1),
                members=[{
                    "Name": "ALICE",
                    "IC": "800101010101",
                    "Shares": 100,
                    "Date": "01/02/2025",
                }],
                total=100,
                path=str(folder / "first.pdf"),
            )
            second = filing(
                folder,
                "S51",
                datetime(2025, 2, 1),
                members=[{
                    "Name": "BOB",
                    "IC": "810101010101",
                    "Shares": 100,
                    "Date": "01/02/2025",
                }],
                total=100,
                path=str(folder / "second.pdf"),
            )
            records = [annual_return, first, second]
            extractor.canonicalize_filings(records)
            row, _, issues = extractor.resolve_company_event_aware(
                folder, records
            )
            self.assertEqual(row["_members"][0]["Name"], "ALICE")
            self.assertIn(
                "SAME_DATE_MEMBER_SNAPSHOT_CONFLICT",
                {item["Code"] for item in issues},
            )

    def test_unreadable_candidate_keeps_state_and_flags_staleness(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Company"
            folder.mkdir()
            annual_return = filing(
                folder,
                "S68",
                datetime(2025, 1, 1),
                members=[member("ALICE", "800101010101", 100)],
                total=100,
            )
            unreadable = filing(
                folder,
                "S51",
                datetime(2025, 2, 1),
                status="UNREADABLE",
            )
            unreadable.warnings.append("No readable text")
            records = [annual_return, unreadable]
            extractor.canonicalize_filings(records)
            row, _, issues = extractor.resolve_company_event_aware(
                folder, records
            )
            self.assertEqual(row["_members"][0]["Name"], "ALICE")
            self.assertIn(
                "POTENTIALLY_STALE_UNREADABLE_FILING",
                {item["Code"] for item in issues},
            )

    def test_highscore_real_pdf_timeline(self):
        root = Path(
            r"D:\CSAI_CLIENTS\Highscore Trading Sdn Bhd "
            r"(fks Highscore Estate Sdn Bhd)"
        )
        if not root.is_dir():
            self.skipTest("Highscore company folder is unavailable")
        paths = [
            root / "AR" / "2025" / "AR Highscore 2025 Approval.pdf",
            root / "Form" / "Section 51"
            / "Highscore Trading - Section 51 ROM dated 20250925.pdf",
            root / "Form" / "Section 58"
            / "Section 58 Highscore dated 20250702.pdf",
            root / "Form" / "Section 58"
            / "Highscore Section 58 dated 20250918 (Appoint & Resign).pdf",
        ]
        records = [
            extractor.build_filing_record(path, root.name)
            for path in paths
        ]
        extractor.canonicalize_filings(records)
        row, _, issues = extractor.resolve_company_event_aware(root, records)
        self.assertEqual(row["Annual Return Date"], "02/08/2025")
        self.assertEqual(row["Total Issued Shares"], 50000)
        self.assertEqual(
            [(item["Name"], item["Shares"]) for item in row["_members"]],
            [("LIM MING KHAM", 50000)],
        )
        director_names = [
            value
            for key, value in row.items()
            if key.startswith("Director") and key.endswith(" Name")
        ]
        self.assertEqual(director_names, ["LIM MING KHAM"])
        self.assertFalse(
            [item for item in issues if item["Severity"] == "CRITICAL"]
        )


if __name__ == "__main__":
    unittest.main()
