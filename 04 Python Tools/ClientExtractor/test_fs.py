"""Focused regression tests for the FS extractor and converter."""

from datetime import date
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fs = load_module("fs_extractor_under_test", HERE / "FS.py")
converter = load_module(
    "fs_converter_under_test",
    HERE.parent / "Convertor" / "FS_to_sqlite.py",
)


class FakePage:
    def __init__(self, layout: str):
        self.layout = layout

    def extract_text(self, extraction_mode=None):
        return self.layout


class FakeReader:
    def __init__(self, *layouts: str):
        self.pages = [FakePage(layout) for layout in layouts]


class ExtractorTests(unittest.TestCase):
    def test_default_head_read_never_calls_ocr(self):
        with (
            patch.object(fs, "PdfReader", return_value=FakeReader("")),
            patch.object(
                fs,
                "ocr_pages",
                side_effect=AssertionError("OCR must be opt-in"),
            ),
        ):
            text, page_count = fs.read_head(Path("sparse.pdf"))

        self.assertEqual(text, "")
        self.assertEqual(page_count, 1)

    def test_opt_in_head_read_uses_ocr_for_sparse_pdf(self):
        recovered = ("Recovered financial statement text " * 10).strip()
        with (
            patch.object(fs, "PdfReader", return_value=FakeReader("")),
            patch.object(fs, "ocr_pages", return_value={0: recovered}) as mocked,
        ):
            text, page_count = fs.read_head(
                Path("sparse.pdf"),
                allow_ocr=True,
            )

        self.assertEqual(text, recovered)
        self.assertEqual(page_count, 1)
        mocked.assert_called_once()

    def test_receipts_are_skipped_without_being_opened(self):
        with tempfile.TemporaryDirectory() as directory:
            fs_folder = Path(directory)
            statement = fs_folder / "Company 2025 Approved.pdf"
            receipt = fs_folder / "Company OR_XB290520260001.pdf"
            statement.touch()
            receipt.touch()
            expected = fs.Candidate(
                statement,
                date(2025, 12, 31),
                True,
                4,
                40,
            )

            with patch.object(fs, "make_candidate", return_value=expected) as mocked:
                selected = fs.select_latest_pdf(fs_folder)

        self.assertEqual(selected, expected)
        mocked.assert_called_once_with(statement, allow_ocr=False)

    def test_ocr_command_line_flag_is_opt_in(self):
        with patch.object(sys, "argv", ["FS.py"]):
            self.assertFalse(fs.parse_arguments().ocr)
        with patch.object(sys, "argv", ["FS.py", "--ocr"]):
            self.assertTrue(fs.parse_arguments().ocr)

    def test_requested_ocr_reports_missing_dependencies(self):
        original_import = __import__

        def import_without_ocr_dependencies(name, *args, **kwargs):
            if name == "numpy":
                raise ImportError("numpy unavailable")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_without_ocr_dependencies):
            with self.assertRaisesRegex(
                RuntimeError,
                "OCR was requested but its optional dependencies are unavailable",
            ):
                fs._ocr_engine()

    def test_date_formats_and_ligatures(self):
        text = "Company's current \ufb01nancial year end date 31/12/2025"
        parsed, explicit = fs.extract_financial_year_end(text)
        self.assertEqual(parsed, date(2025, 12, 31))
        self.assertTrue(explicit)

    def test_audit_firm_boundary_is_removed(self):
        self.assertEqual(
            fs.clean_name("CE GOH & ASSOCIATES Detailed address of audit firm"),
            "CE GOH & ASSOCIATES",
        )

    def test_two_statement_signers(self):
        text = """
        Number of directors signing Statement by Directors 2
        Name of first director who signed Statement by Directors FIRST DIRECTOR
        Disclosure whether the first director is responsible Yes
        Name of second director who signed Statement by Directors SECOND DIRECTOR
        Disclosure whether the second director is responsible No
        Name of third director who signed Statement by Directors
        """
        self.assertEqual(
            fs.extract_statement_signers(text),
            (2, "FIRST DIRECTOR", "SECOND DIRECTOR"),
        )

    def test_signer_does_not_capture_next_page_header(self):
        text = """
        Number of directors signing Statement by Directors 2
        Name of first director who signed Statement by Directors FIRST DIRECTOR
        Company No : 202001000001 Page 8 of 70
        Disclosure whether the first director is responsible Yes
        Name of second director who signed Statement by Directors SECOND DIRECTOR Page 9 of 70
        Type of identification of second director who signed Statement by Directors
        """
        self.assertEqual(
            fs.extract_statement_signers(text),
            (2, "FIRST DIRECTOR", "SECOND DIRECTOR"),
        )

    def test_second_signer_removed_when_count_is_one(self):
        text = """
        Number of directors signing Statement by Directors 1
        Name of first director who signed Statement by Directors FIRST DIRECTOR
        Name of second director who signed Statement by Directors SPURIOUS NAME
        Type of identification of second director who signed Statement by Directors
        """
        count, first, second = fs.extract_statement_signers(text)
        self.assertEqual(count, 1)
        self.assertEqual(first, "FIRST DIRECTOR")
        self.assertIsNone(second)

    def test_declarant_uses_section_251_name(self):
        text = """
        STATUTORY DECLARATION
        Pursuant to Section 251 (1) (b) of the Companies Act 2016
        I, DECLARING DIRECTOR (IC No. 123), being the director primarily
        responsible for financial management, do solemnly declare.
        Before me, COMMISSIONER NAME
        """
        self.assertEqual(
            fs.extract_declarant_name(text, "OTHER DIRECTOR", None),
            "DECLARING DIRECTOR",
        )

    def test_fee_blank_is_null_and_dash_is_zero(self):
        blank = """
        Director's remuneration
        Salaries and other emoluments        1,000        900
        Fees
        Total Director's remuneration       1,000        900
        """
        dash = """
        Director's remuneration
        Salaries and other emoluments          -          -
        Fees                                   -          -
        Total Director's remuneration          -          -
        """
        self.assertIsNone(
            fs.extract_current_director_fee(FakeReader(blank), [blank])
        )
        self.assertEqual(
            fs.extract_current_director_fee(FakeReader(dash), [dash]),
            0,
        )

    def test_fee_uses_company_current_value_in_consolidated_table(self):
        layout = """
        Group Group Company Company
        2025 2024 2025 2024
        Director's remuneration
        Fees                         9,000 8,000 7,000 6,000
        Total Director's remuneration
        """
        self.assertEqual(
            fs.extract_current_director_fee(FakeReader(layout), [layout]),
            7000,
        )

    def test_approved_candidate_wins_same_year(self):
        approved = fs.Candidate(
            Path("Company 2025 Approved.pdf"), date(2025, 12, 31), True, 4, 40
        )
        preview = fs.Candidate(
            Path("MBRS Preview.pdf"), date(2025, 12, 31), True, 4, 40
        )
        self.assertLess(fs.candidate_stage(approved), fs.candidate_stage(preview))


class ConverterTests(unittest.TestCase):
    def sample_row(self):
        row = {column: None for column in fs.COLUMNS}
        row.update(
            {
                "Company": "SAMPLE SDN. BHD.",
                "Source PDF": r"D:\sample.pdf",
                fs.COLUMNS[2]: date(2025, 1, 1),
                fs.COLUMNS[3]: date(2025, 12, 31),
                fs.COLUMNS[4]: date(2026, 6, 10),
                fs.COLUMNS[5]: date(2026, 6, 30),
                fs.COLUMNS[6]: date(2026, 6, 10),
                fs.COLUMNS[7]: "FIRST DIRECTOR",
                fs.COUNT_COLUMN: 2,
                fs.COLUMNS[9]: "FIRST DIRECTOR",
                fs.COLUMNS[10]: "SECOND DIRECTOR",
                fs.COLUMNS[11]: "AUDIT FIRM",
                fs.FEE_COLUMN: 1250.5,
            }
        )
        return row

    def test_workbook_to_sqlite_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workbook = root / "FS.xlsx"
            database = root / "FS.db"
            fs.write_workbook([self.sample_row()], workbook)
            rows = converter.load_rows(workbook)
            converter.create_database(database, rows)
            connection = sqlite3.connect(database)
            try:
                imported = connection.execute('SELECT * FROM "FS"').fetchone()
                self.assertEqual(imported[0], "SAMPLE SDN. BHD.")
                self.assertEqual(imported[8], 2)
                self.assertEqual(imported[10], "SECOND DIRECTOR")
                self.assertEqual(imported[12], 1250.5)
                self.assertEqual(
                    connection.execute("PRAGMA integrity_check").fetchone()[0],
                    "ok",
                )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
