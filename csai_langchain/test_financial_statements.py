import unittest
from dataclasses import asdict, is_dataclass

from csai_langchain.routing.router import Router
from csai_langchain.service.csai_service import CSAIService


class FinancialStatementIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.router = Router()
        cls.service = CSAIService()

    @classmethod
    def tearDownClass(cls):
        cls.service.close()

    @classmethod
    def query(cls, question):
        response = cls.service.execute(cls.router.detect(question))
        return asdict(response) if is_dataclass(response) else response

    def test_financial_statement_fields_for_company(self):
        response = self.query(
            "Show the current financial year end date and name of the audit "
            "firm of VL REALTY MANAGEMENT SERVICES SDN BHD"
        )

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["intent"], "financial_statement_information")
        self.assertEqual(response["sources"], ["FS.db:FS"])
        self.assertEqual(response["count"], 1)
        self.assertEqual(
            response["results"][0]["Company's current financial year end date"],
            "2025-12-31",
        )
        self.assertEqual(
            response["results"][0]["Name of audit firm"],
            "Y. H. CHANG & PARTNERS",
        )

    def test_second_signer_and_current_year_fee_fields(self):
        response = self.query(
            "What are the current financial year end date, name of second "
            "director who signed Statement by Directors and director's "
            "remuneration fees of ACTION MULTIPLE SDN BHD?"
        )

        self.assertEqual(response["intent"], "financial_statement_information")
        self.assertEqual(response["sources"], ["FS.db:FS"])
        self.assertEqual(
            response["results"][0][
                "Name of second director who signed Statement by Directors"
            ],
            "LEE MOI TIANG",
        )
        self.assertIn(
            "Director's remuneration - Fees (Current Financial Year)",
            response["results"][0],
        )

    def test_generic_financial_year_end_keeps_legacy_auditor_route(self):
        response = self.query(
            "What is the financial year end of ACTION MULTIPLE SDN BHD?"
        )

        self.assertEqual(response["intent"], "auditor")
        self.assertEqual(response["sources"], ["auditors.db:Sheet1"])
        self.assertEqual(response["financial_year_end"], "31 OCTOBER")

    def test_multi_database_query_includes_financial_statements(self):
        response = self.query(
            "Show the annual return date, date of financial statements "
            "approved by Board of Directors and beneficial owners of "
            "ACTION MULTIPLE SDN BHD."
        )

        self.assertEqual(response["intent"], "multi_intent")
        self.assertEqual(response["section_count"], 3)
        self.assertEqual(
            [section["intent"] for section in response["sections"]],
            [
                "company_information",
                "financial_statement_information",
                "beneficial_owner",
            ],
        )
        self.assertEqual(
            response["sources"],
            [
                "csai_master.db:Client_Master",
                "FS.db:FS",
                "ebos_master.db:EBOS_Master",
            ],
        )

    def test_circulation_phrase_does_not_trigger_shareholders(self):
        response = self.query(
            "Show annual return date and date of circulation of financial "
            "statements and reports to members of ACTION MULTIPLE SDN BHD."
        )

        self.assertEqual(response["intent"], "multi_intent")
        self.assertEqual(
            [section["intent"] for section in response["sections"]],
            ["company_information", "financial_statement_information"],
        )

    def test_all_company_financial_statement_query(self):
        response = self.query(
            "List all companies with date of statutory declaration"
        )

        self.assertEqual(response["intent"], "financial_statement_information")
        self.assertEqual(response["sources"], ["FS.db:FS"])
        self.assertGreaterEqual(response["count"], 1)
        self.assertTrue(
            all(
                "Date of Statutory Declaration" in record
                for record in response["results"]
            )
        )


if __name__ == "__main__":
    unittest.main()
