import importlib.util
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("extract_client_final.py")
SPEC = importlib.util.spec_from_file_location("extract_client_final", MODULE_PATH)
extractor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extractor)


class SourcePriorityTests(unittest.TestCase):
    def test_section51_must_be_strictly_newer(self):
        base = datetime(2025, 7, 27)
        self.assertFalse(
            extractor.should_use_section51(
                datetime(2025, 6, 20),
                base,
                [{"Name": "Older member"}],
            )
        )
        self.assertFalse(
            extractor.should_use_section51(
                base,
                base,
                [{"Name": "Same-date member"}],
            )
        )
        self.assertTrue(
            extractor.should_use_section51(
                datetime(2025, 11, 13),
                base,
                [{"Name": "Newer member"}],
            )
        )

    def test_latest_dated_section27_wins(self):
        older = """CHANGE OF COMPANY NAME
Proposed Company Name HIGHSCORE TRADING SDN. BHD.
Date of Application :14/07/2025
"""
        newer = """CHANGE OF COMPANY NAME
Proposed Company Name MY HANTAR SDN. BHD.
Date of Application :09/06/2026
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            old_pdf = folder / "Section 27 old.pdf"
            new_pdf = folder / "Section 27 new.pdf"
            old_pdf.touch()
            new_pdf.touch()
            texts = {old_pdf: older, new_pdf: newer}
            with patch.object(
                extractor,
                "read_pdf",
                side_effect=lambda path: texts[path],
            ):
                self.assertEqual(
                    extractor.find_section27_new_name(folder),
                    "MY HANTAR SDN. BHD.",
                )

    def test_section17_prose_incorporation_date(self):
        text = (
            "is, on and from the 8h day of August 2017, "
            "incorporated under the Companies Act"
        )
        self.assertEqual(
            extractor.extract_incorporation_date(text),
            "08/08/2017",
        )


@unittest.skipUnless(
    Path(r"D:\CSAI_CLIENTS").exists(),
    "Original company folders are not available",
)
class OriginalCompanyIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(r"D:\CSAI_CLIENTS")
        cls.folders = {folder.name.lower(): folder for folder in cls.root.iterdir()}

    def find_folder(self, fragment):
        return next(
            folder
            for name, folder in self.folders.items()
            if fragment in name
        )

    def test_ecopmin_has_section68_and_it_is_newer_than_section51(self):
        folder = self.find_folder("ecopmin")
        section68 = extractor.latest_section68(folder)
        self.assertIsNotNone(section68)
        self.assertEqual(
            extractor.annual_return_date(extractor.read_pdf(section68)),
            "27/07/2025",
        )
        _, section51_date, _ = extractor.find_latest_section51(folder)
        self.assertEqual(section51_date, "20/06/2025")

    def test_my_hantar_latest_section27_name(self):
        folder = self.find_folder("my hantar")
        self.assertEqual(
            extractor.find_section27_new_name(folder),
            "MY HANTAR SDN. BHD.",
        )

    def test_latest_section51_totals(self):
        expected = {
            "movement first": "800000",
            "ocean view": "50100",
            "telun": "3000",
        }
        for fragment, total in expected.items():
            with self.subTest(company=fragment):
                folder = self.find_folder(fragment)
                section51, _, _ = extractor.find_latest_section51(folder)
                self.assertIsNotNone(section51)
                text = extractor.read_pdf(section51)
                self.assertEqual(extractor.extract_total_shares_s51(text), total)

    @unittest.skipUnless(extractor.OCR_AVAILABLE, "OCR backend is not installed")
    def test_scanned_incorporation_dates(self):
        expected = {
            "ecopmin": "27/07/2020",
            "movement first": "08/08/2017",
        }
        for fragment, incorporation_date in expected.items():
            with self.subTest(company=fragment):
                folder = self.find_folder(fragment)
                self.assertEqual(
                    extractor.find_incorporation_date_in_folder(folder),
                    incorporation_date,
                )


if __name__ == "__main__":
    unittest.main()
