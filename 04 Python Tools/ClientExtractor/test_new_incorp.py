import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("new_incorp.py")
SPEC = importlib.util.spec_from_file_location("new_incorp", MODULE_PATH)
extractor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = extractor
SPEC.loader.exec_module(extractor)


S14_TEXT = """
COMPANIES ACT 2016
Section 14
APPLICATION FOR REGISTRATION OF A COMPANY
PARTICULARS OF COMPANY
Proposed name TEST COMPANY SDN. BHD.
Lodging Reference No ACN123
Purpose N - NEW INCORPORATION
Company Type S - LIMITED BY SHARES
Sub Type SDN. BHD.
Incorporation Date 09/12/2024
Registration No. 202401051970 (1597813-X)
General nature of business MSIC Code
1 Retail sale of bakery products 47216
2 Wholesale of bakery products 46324
Business Description RETAIL AND WHOLESALE
Registered Address 1 TEST STREET 08000 KEDAH MALAYSIA
Email company@example.com
Office No 0123456789
Fax number NIL
Business Address 2 TEST STREET 08000 KEDAH MALAYSIA
Office No NIL
Fax number NIL
PARTICULARS OF DIRECTOR
Director Name TEST PERSON
ID Type NRIC
Identification No 811229025695
Nationality MALAYSIA
Address 3 TEST STREET 08000 KEDAH MALAYSIA
Date of birth 29/12/1981
Race CHINESE
Email person@example.com
PARTICULARS OF MEMBER
Member Name TEST PERSON
ID Type NRIC
Identification No 811229025695
Nationality MALAYSIA
Address 3 TEST STREET 08000 KEDAH MALAYSIA
Race CHINESE
Email person@example.com
Price per share 1.0000
Class of share Ordinary
Number of share 1
Declaration
Name : TEST LODGER
Date of Application :09/12/2024
ATTENTION:
Lodger Information
Name TEST LODGER
NRIC 760228025696
Prescribed body MAICSA
License No/Membership No MAICSA123
Address 4 TEST STREET 08000 KEDAH MALAYSIA
Phone No. 0111111111
Email lodger@example.com
"""


EBOS_TEXT = """
NOTIFICATION OF BENEFICIAL OWNERSHIP INFORMATION
Division 8A, 60B (3), Companies Act 2016 Submission Number BOU20250525000138
Date & Time Received 25/05/2025 10:13 PM
PARTICULARS OF COMPANY
COMPANY NAME TEST COMPANY SDN. BHD.
COMPANY NO 202401051970 (1597813-X)
STATUS EXISTING
PARTICULARS OF BENEFICIAL OWNERSHIP
TYPE OF BO APPLICATION BENEFICIAL OWNER
STATUS NEW
DATE OF BECOMING BO 09/12/2024
DATE OF DATA RECORDED 25/05/2025
TYPE INDIVIDUAL
CATEGORY INDIVIDUAL
NAME TEST PERSON
IDENTIFICATION NO. 811229025695 DATE OF BIRTH 29/12/1981
GENDER MALE RACE CHINESE
NATIONALITY MALAYSIA CITIZENSHIP MALAYSIAN
DESIGNATION/POSITION IN THE
COMPANY
DIRECTOR
RESIDENTIAL ADDRESS 3 TEST STREET
08000 KEDAH
MALAYSIA
BUSINESS ADDRESS NIL
EMAIL latest@example.com CONTACT NO. 0126220099
TYPE OF BO DIRECT OWNERSHIP
Criteria A - Holds directly in not less than 20% of the shares of the company
Criteria B - Holds directly in not less than 20% of the voting shares of the company
Criteria C - Has the right to exercise control
PERCENTAGE % Criteria A - Direct Ownership: 100.0000
Criteria B - Voting Shares: 100.0000
Criteria C - N/A
DECLARATION
NAME TEST LODGER
DATE OF APPLICATION 25/05/2025
ATTENTION
LODGER INFORMATION
NAME TEST LODGER
IDENTIFICATION NO. 760228025696
ADDRESS 4 TEST STREET
08000 KEDAH
MALAYSIA
EMAIL ADDRESS lodger@example.com
PHONE NO. 0111111111
PRACTISING CERTIFICATE NO. 20190001
PROFESSIONAL BODY TYPE MAICSA
LICENSE NO. /MEMBERSHIP NO. MAICSA123
SURUHANJAYA SYARIKAT MALAYSIA
"""


def candidate(path, family, when, *, revision=0, submission="", digest="x"):
    return extractor.Candidate(
        family=family,
        path=Path(path),
        relative_path=str(path),
        text="",
        sha256=digest,
        registration_no="202401051970 (1597813-X)",
        registration_match=2,
        document_datetime=when,
        filename_datetime=None,
        mtime_ns=1,
        revision=revision,
        submission_number=submission,
    )


class NewIncorpTests(unittest.TestCase):
    def test_section14_parser_extracts_company_people_and_contacts(self):
        parsed = extractor.parse_section14(S14_TEXT)
        self.assertEqual(parsed["company"]["Company Email"], "company@example.com")
        self.assertEqual(parsed["company"]["Registered Address"], "1 TEST STREET 08000 KEDAH MALAYSIA")
        self.assertEqual(parsed["activities"][1]["MSIC Code"], "46324")
        self.assertEqual(parsed["directors"][0]["Identification No"], "811229025695")
        self.assertEqual(parsed["directors"][0]["Email"], "person@example.com")
        self.assertEqual(parsed["members"][0]["Price per Share"], "1.0000")
        self.assertEqual(parsed["lodger"]["Phone No"], "0111111111")

    def test_ebos_parser_extracts_same_line_fields_and_percentages(self):
        parsed = extractor.parse_ebos(EBOS_TEXT)
        self.assertEqual(parsed["header"]["Submission Number"], "BOU20250525000138")
        self.assertEqual(parsed["header"]["Received DateTime"], "2025-05-25 22:13:00")
        owner = parsed["beneficial_owners"][0]
        self.assertEqual(owner["DOB"], "29/12/1981")
        self.assertEqual(owner["Race"], "CHINESE")
        self.assertEqual(owner["Citizenship"], "MALAYSIAN")
        self.assertEqual(owner["Contact No"], "0126220099")
        self.assertEqual(owner["Type of BO"], "DIRECT OWNERSHIP")
        self.assertEqual(owner["Criteria A - Direct Ownership %"], "100.0000")
        self.assertEqual(owner["Criteria C"], "N/A")

    def test_latest_ranking_uses_received_time_and_revision(self):
        early = candidate("E-BOS/one.pdf", "EBOS", datetime(2025, 5, 25, 16, 7), submission="BOU84", digest="one")
        late = candidate("E-BOS/two.pdf", "EBOS", datetime(2025, 5, 25, 22, 13), submission="BOU138", digest="two")
        self.assertIs(extractor.select_latest_candidate([early, late]), late)
        base = candidate("Form/SuperForm.pdf", "S14", datetime(2024, 12, 9), digest="base")
        revised = candidate("Form/SuperForm (R1).pdf", "S14", datetime(2024, 12, 9), revision=1, digest="revised")
        self.assertIs(extractor.select_latest_candidate([base, revised]), revised)

    def test_hash_deduplication_keeps_preferred_copy(self):
        audit = candidate("Statutory Audit/SuperForm (R1).pdf", "S14", datetime(2024, 12, 9), revision=1, digest="same")
        form = candidate("Form/SuperForm (R1).pdf", "S14", datetime(2024, 12, 9), revision=1, digest="same")
        deduplicated = extractor.deduplicate_candidates([audit, form])
        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0].path, form.path)

    def test_contact_enrichment_prefers_latest_ebos_without_overwrite(self):
        current = {
            "Director1 Name": "TEST PERSON",
            "Director1 IC": "811229025695",
            "Director1 Email": "",
            "Director1 Contact No": "",
            "Member1 Name": "TEST PERSON",
            "Member1 ID No": "811229025695",
            "Member1 Email": "existing@example.com",
        }
        enriched = extractor.enrich_current_people(
            current,
            extractor.parse_section14(S14_TEXT),
            extractor.parse_ebos(EBOS_TEXT),
        )
        self.assertEqual(enriched["Director1 Email"], "latest@example.com")
        self.assertEqual(enriched["Director1 Contact No"], "0126220099")
        self.assertEqual(enriched["Member1 Email"], "existing@example.com")
        self.assertEqual(enriched["Member1 Contact No"], "0126220099")

    def test_registration_conflict_is_rejected(self):
        self.assertEqual(extractor.registration_state("202401051970 (1597813-X)", "202401051970 (1597813-X)"), 2)
        self.assertEqual(extractor.registration_state("202499999999", "202401051970"), 0)
        self.assertEqual(extractor.registration_state("", "202401051970"), 1)

    def test_sheet_names_are_valid_and_unique(self):
        used = set()
        first = extractor.safe_sheet_name(1, "A/B:*? Company With A Very Long Name", used)
        second = extractor.safe_sheet_name(1, "A/B:*? Company With A Very Long Name", used)
        self.assertLessEqual(len(first), 31)
        self.assertNotRegex(first, r"[\\/*?:\[\]]")
        self.assertNotEqual(first, second)

    def test_folder_lookup_normalizes_non_breaking_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual = root / "Ocean View Holidays Sdn.\xa0Bhd"
            actual.mkdir()
            _, normalized = extractor.resolve_client_directories(root)
            self.assertEqual(
                normalized[extractor.normalize_name("Ocean View Holidays Sdn. Bhd")],
                actual,
            )

    def test_real_hosay_sources_when_available(self):
        root = Path(r"D:\CSAI_CLIENTS\Hosay 3 Bakery Sdn. Bhd")
        if not root.is_dir():
            self.skipTest("Hosay sample folder is unavailable")
        registration = "202401051970 (1597813-X)"
        s14 = extractor.select_latest_candidate(extractor.discover_candidates(root, registration, "S14", False))
        ebos = extractor.select_latest_candidate(extractor.discover_candidates(root, registration, "EBOS", False))
        self.assertEqual(s14.relative_path, r"Form\SuperForm Hosay 3 Bakery Sdn bhd (R1).pdf")
        self.assertTrue(ebos.relative_path.endswith("20250525-2.pdf"))
        self.assertEqual(ebos.parsed["beneficial_owners"][0]["Name"], "TAM WEE SEONG")
        self.assertEqual(ebos.parsed["beneficial_owners"][0]["Criteria A - Direct Ownership %"], "100.0000")
        self.assertEqual(ebos.parsed["beneficial_owners"][1]["Status"], "CESSATION")


if __name__ == "__main__":
    unittest.main()
