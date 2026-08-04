import math
import sqlite3
from dataclasses import asdict, is_dataclass

from csai_langchain.config.settings import CLIENT_DB
from csai_langchain.routing.router import Router
from csai_langchain.service.csai_service import CSAIService


AUDITOR_RECORD_KEYS = [
    "Company Name",
    "Reg No",
    "Financial Year End",
    "Auditor Firm No",
    "Auditor Name",
    "Auditor Address",
    "UpdatedAt",
]


DIRECTOR_RECORD_KEYS = [
    "Company Name",
    "Reg No",
    "Name",
    "IC",
    "ID Type",
    "DOB",
    "Passport Expiry",
    "Nationality",
    "Citizenship",
    "Race",
    "Gender",
    "Residential Address",
    "Service Address",
    "Designation",
    "Business Occupation",
    "Email",
    "Contact No",
    "Appointment Date",
]


SHAREHOLDER_RECORD_KEYS = [
    "Company Name",
    "Reg No",
    "Type",
    "Name",
    "ID Type",
    "ID No",
    "Nationality",
    "Race",
    "Gender",
    "DOB",
    "Address",
    "Shares",
    "Share Type",
    "Analysis",
]


def database_columns(table_name):

    database_uri = (
        CLIENT_DB.resolve().as_uri()
        + "?mode=ro"
    )

    with sqlite3.connect(
        database_uri,
        uri=True
    ) as connection:

        return [
            row[1]
            for row in connection.execute(
                f'PRAGMA table_info("{table_name}")'
            )
        ]


def contains_nan(value):

    if isinstance(value, float):
        return math.isnan(value)

    if isinstance(value, dict):
        return any(
            contains_nan(item)
            for item in value.values()
        )

    if isinstance(value, (list, tuple)):
        return any(
            contains_nan(item)
            for item in value
        )

    return False


TEST_CASES = [

    {
        "name": "Company directors",
        "question": (
            "Who are the directors of Action Multiple?"
        ),
        "expected_intent": "director",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_count": 3,
        "expected_result_contains": [
            {
                "Name": "LEE MOI TIANG",
            },
            {
                "Name": "KHOR PENG CHAI",
            },
            {
                "Name": "KHOR KIAN ZHEN",
            },
        ],
    },

    {
        "name": "Company shareholders",
        "question": (
            "List shareholders of Action Multiple"
        ),
        "expected_intent": "shareholder",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_count": 1,
        "expected_result_contains": [
            {
                "Name": "LEE MOI TIANG",
                "Shares": 50000,
                "Share Type": "ORDINARY SHARES",
            },
        ],
    },

    {
        "name": "Company members remain shareholders",
        "question": (
            "Who are the members of Action Multiple?"
        ),
        "expected_intent": "shareholder",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_count": 1,
        "expected_result_contains": [
            {
                "Name": "LEE MOI TIANG",
            },
        ],
    },

    {
        "name": "Beneficial owners",
        "question": (
            "Beneficial owners of Action Multiple"
        ),
        "expected_intent": "beneficial_owner",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_count": 1,
        "expected_result_contains": [
            {
                "Name": "LEE MOI TIANG",
                "Source PDF": (
                    "EBOS ACTION MULTIPLE_"
                    "INFORMATION_UPDATE_ODT-20250818.pdf"
                ),
                "Type": "INDIVIDUAL",
                "Type of BO": "DIRECT OWNERSHIP",
                "Criteria A - Direct Ownership %": (
                    "100.0000"
                ),
                "Criteria B - Voting Shares %": (
                    "100.0000"
                ),
                "Direct Ownership %": "100.0000",
                "Voting Shares %": "100.0000",
                "Criteria C - N/A": None,
                "Date of Cessation": None,
            },
        ],
        "expected_result_keys": [
            "Source PDF",
            "PDF Date",
            "Submission No",
            "Date Received",
            "Time Received",
            "Company Name",
            "Company No",
            "Company Status",
            "BO Status",
            "Date of Becoming BO",
            "Date of Cessation",
            "Reason",
            "Date of Data Recorded",
            "Type",
            "Category",
            "Name",
            "IC",
            "DOB",
            "Gender",
            "Race",
            "Nationality",
            "Citizenship",
            "Designation",
            "Residential Address",
            "Business Address",
            "Email",
            "Contact No",
            "Type of BO",
            "Criteria A - Direct Ownership %",
            "Criteria B - Voting Shares %",
            "Criteria C - N/A",
            "Declaration Name",
            "Date of Application",
            "Lodger Name",
            "Lodger IC",
            "Lodger Address",
            "Lodger Email",
            "Lodger Phone No",
            "Practising Cert No",
            "Professional Body Type",
            "License / Membership No",
            "UpdatedAt",
            "Company",
            "Master Company Name",
            "Master Company No",
            "Master Company Status",
            "Direct Ownership %",
            "Voting Shares %",
        ],
    },

    {
        "name": "Complete EBOS records",
        "question": (
            "Show the complete EBOS records, including "
            "residential address, business address, "
            "contact details, ownership percentages and "
            "filing information, for ACTION MULTIPLE "
            "SDN BHD."
        ),
        "expected_intent": "beneficial_owner",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_count": 1,
        "expected_sources": [
            "EBOS_Master",
        ],
        "expected_result_contains": [
            {
                "Name": "LEE MOI TIANG",
                "Residential Address": (
                    "NO. 3355, JALAN ROZHAN TAMAN "
                    "INDUSTRI ALMA JAYA 14000 BUKIT "
                    "MERTAJAM PULAU PINANG MALAYSIA"
                ),
                "Type of BO": "DIRECT OWNERSHIP",
                "Direct Ownership %": "100.0000",
                "Submission No": "BOU20250821000979",
            },
        ],
    },

    {
        "name": "Person directorship",
        "question": (
            "Which companies is KHOR PENG CHAI "
            "appointed as director?"
        ),
        "expected_intent": "person_directorship",
        "expected_status": "success",
        "expected_person": "KHOR PENG CHAI",
        "expected_count": 11,
        "expected_result_contains": [
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
            },
            {
                "Company Name": (
                    "CTW GLOBAL SDN. BHD."
                ),
            },
        ],
    },

    {
        "name": "Person-first directorship",
        "question": (
            "Khor Peng Chai is director of "
            "what company"
        ),
        "expected_intent": "person_directorship",
        "expected_status": "success",
        "expected_person": "KHOR PENG CHAI",
        "expected_count": 11,
        "expected_sources": [
            "Client_Master",
        ],
    },

    {
        "name": "Person beneficial-ownership history",
        "question": (
            "Khor Peng Chai is what company's BO?"
        ),
        "expected_intent": (
            "person_beneficial_ownership"
        ),
        "expected_status": "success",
        "expected_person": "KHOR PENG CHAI",
        "expected_count": 23,
        "expected_sources": [
            "EBOS_Master",
        ],
        "expected_result_contains": [
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "BO Status": "NEW",
                "Name": "KHOR PENG CHAI",
            },
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "BO Status": "CESSATION",
                "Name": "KHOR PENG CHAI",
            },
            {
                "Company Name": (
                    "HIGHSCORE TRADING SDN. BHD."
                ),
                "Filed Company Name": (
                    "HIGHSCORE ESTATE SDN. BHD."
                ),
                "BO Status": "NEW",
            },
        ],
    },

    {
        "name": "Person-first beneficial ownership",
        "question": (
            "Khor Peng Chai is BO of what company?"
        ),
        "expected_intent": (
            "person_beneficial_ownership"
        ),
        "expected_status": "success",
        "expected_person": "KHOR PENG CHAI",
        "expected_count": 23,
        "expected_sources": [
            "EBOS_Master",
        ],
    },

    {
        "name": "Person company associations",
        "question": (
            "Khor Peng Chai is what company's "
            "shareholder?"
        ),
        "expected_intent": "person_shareholding",
        "expected_status": "success",
        "expected_person": "KHOR PENG CHAI",
        "expected_count": 11,
        "expected_sources": [
            "Client_Master",
        ],
        "expected_unique_result_field": (
            "Reg No"
        ),
        "expected_result_contains": [
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "Roles": [
                    "Director",
                ],
            },
            {
                "Company Name": (
                    "CTW LOGISTICS SDN. BHD."
                ),
                "Roles": [
                    "Director",
                    "Shareholder",
                ],
                "Shares": 2,
            },
            {
                "Company Name": (
                    "LT JAYA MARKETING SDN. BHD."
                ),
            },
        ],
    },

    {
        "name": "Person-first shareholding",
        "question": (
            "Khor Peng Chai is shareholder of "
            "what company"
        ),
        "expected_intent": "person_shareholding",
        "expected_status": "success",
        "expected_person": "KHOR PENG CHAI",
        "expected_count": 11,
        "expected_sources": [
            "Client_Master",
        ],
    },

    {
        "name": "Person-first member shareholding",
        "question": (
            "Khor Peng Chai is member of "
            "what company"
        ),
        "expected_intent": "person_shareholding",
        "expected_status": "success",
        "expected_person": "KHOR PENG CHAI",
        "expected_count": 11,
        "expected_sources": [
            "Client_Master",
        ],
    },

    {
        "name": "Reversed person shareholding",
        "question": (
            "Khor Peng Chai is a shareholder "
            "in which companies?"
        ),
        "expected_intent": "person_shareholding",
        "expected_status": "success",
        "expected_person": "KHOR PENG CHAI",
        "expected_count": 11,
        "expected_sources": [
            "Client_Master",
        ],
    },

    {
        "name": "List person shareholder companies",
        "question": (
            "List all the companies that "
            "Khor Peng Chai is the shareholder"
        ),
        "expected_intent": "person_shareholding",
        "expected_status": "success",
        "expected_person": "KHOR PENG CHAI",
        "expected_count": 11,
        "expected_sources": [
            "Client_Master",
        ],
    },

    {
        "name": "List person director companies",
        "question": (
            "List all the companies that "
            "Khor Peng Chai is a director"
        ),
        "expected_intent": "person_directorship",
        "expected_status": "success",
        "expected_person": "KHOR PENG CHAI",
        "expected_count": 11,
        "expected_sources": [
            "Client_Master",
        ],
    },

    {
        "name": "List person BO companies",
        "question": (
            "List all the companies that "
            "Khor Peng Chai is a BO"
        ),
        "expected_intent": (
            "person_beneficial_ownership"
        ),
        "expected_status": "success",
        "expected_person": "KHOR PENG CHAI",
        "expected_count": 23,
        "expected_sources": [
            "EBOS_Master",
        ],
    },

    {
        "name": "Combined person role status",
        "question": (
            "Show Khor Peng Chai director, BO "
            "and shareholder status"
        ),
        "expected_intent": "person_status",
        "expected_status": "success",
        "expected_person": "KHOR PENG CHAI",
        "expected_count": 35,
        "expected_sources": [
            "Client_Master",
            "EBOS_Master",
        ],
        "expected_result_field_counts": {
            "field": "Role",
            "values": {
                "Director": 11,
                "Beneficial Owner": 23,
                "Shareholder": 1,
            },
        },
    },

    {
        "name": "Company auditor",
        "question": (
            "Who is the auditor of Action Multiple?"
        ),
        "expected_intent": "auditor",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_auditor": (
            "Y.H.CHANG & PARTNERS"
        ),
        "expected_financial_year_end": (
            "31 OCTOBER"
        ),
        "expected_count": 1,
        "expected_sources": [
            "auditors.db:Sheet1",
        ],
        "expected_result_contains": [
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "Auditor Firm No": "AF1432",
                "Auditor Name": (
                    "Y.H.CHANG & PARTNERS"
                ),
                "Financial Year End": (
                    "31 OCTOBER"
                ),
            },
        ],
        "expected_result_keys": (
            AUDITOR_RECORD_KEYS
        ),
        "expected_nonempty_result_fields": [
            "UpdatedAt",
        ],
    },

    {
        "name": "Company financial year end",
        "question": (
            "What is the financial year-end of "
            "Action Multiple?"
        ),
        "expected_intent": "auditor",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_auditor": (
            "Y.H.CHANG & PARTNERS"
        ),
        "expected_financial_year_end": (
            "31 OCTOBER"
        ),
        "expected_count": 1,
        "expected_sources": [
            "auditors.db:Sheet1",
        ],
        "expected_result_contains": [
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "Financial Year End": (
                    "31 OCTOBER"
                ),
            },
        ],
        "expected_result_keys": (
            AUDITOR_RECORD_KEYS
        ),
        "expected_nonempty_result_fields": [
            "UpdatedAt",
        ],
    },

    {
        "name": "Financial year end companies",
        "question": (
            "Which companies have financial year end "
            "31 December?"
        ),
        "expected_intent": (
            "auditor_financial_year_end"
        ),
        "expected_status": "success",
        "expected_financial_year_end": (
            "31 DECEMBER"
        ),
        "expected_count": 19,
        "expected_sources": [
            "auditors.db:Sheet1",
        ],
        "expected_sorted_result_field": (
            "Company Name"
        ),
        "expected_result_keys": (
            AUDITOR_RECORD_KEYS
        ),
        "expected_nonempty_result_fields": [
            "UpdatedAt",
        ],
    },

    {
        "name": "Abbreviated financial year end",
        "question": (
            "Which companies have FYE 31 Dec?"
        ),
        "expected_intent": (
            "auditor_financial_year_end"
        ),
        "expected_status": "success",
        "expected_financial_year_end": (
            "31 DECEMBER"
        ),
        "expected_count": 19,
        "expected_result_keys": (
            AUDITOR_RECORD_KEYS
        ),
        "expected_nonempty_result_fields": [
            "UpdatedAt",
        ],
    },

    {
        "name": "Month-only financial year end",
        "question": (
            "Which companies have a December "
            "financial year end?"
        ),
        "expected_intent": (
            "auditor_financial_year_end"
        ),
        "expected_status": "success",
        "expected_financial_year_end": "DECEMBER",
        "expected_count": 19,
        "expected_result_keys": (
            AUDITOR_RECORD_KEYS
        ),
        "expected_nonempty_result_fields": [
            "UpdatedAt",
        ],
    },

    {
        "name": "Month-first financial year end",
        "question": (
            "Which companies have FYE December 31st?"
        ),
        "expected_intent": (
            "auditor_financial_year_end"
        ),
        "expected_status": "success",
        "expected_financial_year_end": (
            "31 DECEMBER"
        ),
        "expected_count": 19,
        "expected_result_keys": (
            AUDITOR_RECORD_KEYS
        ),
        "expected_nonempty_result_fields": [
            "UpdatedAt",
        ],
    },

    {
        "name": "All company financial year ends",
        "question": (
            "What is the financial year end of "
            "all companies?"
        ),
        "expected_intent": (
            "auditor_financial_year_end"
        ),
        "expected_status": "success",
        "expected_financial_year_end": "ALL",
        "expected_count": 80,
        "expected_sources": [
            "auditors.db:Sheet1",
        ],
        "expected_unique_result_field": (
            "Reg No"
        ),
        "expected_sorted_result_field": (
            "Company Name"
        ),
        "expected_result_keys": (
            AUDITOR_RECORD_KEYS
        ),
        "expected_nonempty_result_fields": [
            "UpdatedAt",
        ],
    },

    {
        "name": "Complete company auditor data",
        "question": (
            "Show all auditor data for Action Multiple"
        ),
        "expected_intent": "auditor",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_financial_year_end": (
            "31 OCTOBER"
        ),
        "expected_count": 1,
        "expected_result_keys": (
            AUDITOR_RECORD_KEYS
        ),
        "expected_nonempty_result_fields": [
            "UpdatedAt",
        ],
    },

    {
        "name": "Missing financial year end",
        "question": (
            "Which companies have a financial "
            "year end?"
        ),
        "expected_intent": (
            "auditor_financial_year_end"
        ),
        "expected_status": "not_found",
        "expected_financial_year_end": "",
        "expected_count": 0,
    },

    {
        "name": "Unmatched financial year end",
        "question": (
            "Which companies have FYE 29 February?"
        ),
        "expected_intent": (
            "auditor_financial_year_end"
        ),
        "expected_status": "not_found",
        "expected_financial_year_end": (
            "29 FEBRUARY"
        ),
        "expected_count": 0,
    },

    {
        "name": "Company auditor alias",
        "question": (
            "Who is the auditor for AMSB?"
        ),
        "expected_intent": "auditor",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_auditor": (
            "Y.H.CHANG & PARTNERS"
        ),
        "expected_count": 1,
    },

    {
        "name": "Auditor-only company name",
        "question": (
            "Who audits Highscore Estate?"
        ),
        "expected_intent": "auditor",
        "expected_status": "success",
        "expected_company": (
            "HIGHSCORE ESTATE SDN. BHD."
        ),
        "expected_auditor": (
            "Y.H.CHANG & PARTNERS"
        ),
        "expected_count": 1,
        "expected_result_contains": [
            {
                "Company Name": (
                    "HIGHSCORE ESTATE SDN. BHD."
                ),
                "Auditor Name": (
                    "Y.H.CHANG & PARTNERS"
                ),
            },
        ],
        "expected_result_keys": (
            AUDITOR_RECORD_KEYS
        ),
    },

    {
        "name": "Auditor company alias remapped by registration",
        "question": (
            "Who audits HIGHSCORE?"
        ),
        "expected_intent": "auditor",
        "expected_status": "success",
        "expected_company": (
            "HIGHSCORE ESTATE SDN. BHD."
        ),
        "expected_auditor": (
            "Y.H.CHANG & PARTNERS"
        ),
        "expected_count": 1,
    },

    {
        "name": "YH Chang companies",
        "question": (
            "Which companies are under "
            "Y.H.CHANG & PARTNERS?"
        ),
        "expected_intent": "auditor_companies",
        "expected_status": "success",
        "expected_auditor": (
            "Y.H.CHANG & PARTNERS"
        ),
        "expected_count": 35,
        "expected_sources": [
            "auditors.db:Sheet1",
        ],
        "expected_unique_result_field": (
            "Reg No"
        ),
        "expected_result_contains": [
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "Auditor Name": (
                    "Y.H.CHANG & PARTNERS"
                ),
            },
            {
                "Company Name": (
                    "FAVOUREX SDN. BHD."
                ),
                "Auditor Name": (
                    "Y.H.CHANG & PARTNERS"
                ),
            },
            {
                "Company Name": (
                    "HIGHSCORE ESTATE SDN. BHD."
                ),
                "Auditor Name": (
                    "Y.H.CHANG & PARTNERS"
                ),
            },
            {
                "Company Name": (
                    "INSIGHT PROFIT SDN. BHD."
                ),
                "Auditor Name": (
                    "Y.H.CHANG & PARTNERS"
                ),
            },
        ],
        "expected_result_keys": (
            AUDITOR_RECORD_KEYS
        ),
        "expected_nonempty_result_fields": [
            "UpdatedAt",
        ],
    },

    {
        "name": "Alan Yoon companies",
        "question": (
            "Which companies are under "
            "Alan Yoon Associates?"
        ),
        "expected_intent": "auditor_companies",
        "expected_status": "success",
        "expected_auditor": (
            "ALAN YOON ASSOCIATES"
        ),
        "expected_count": 27,
    },

    {
        "name": "TNL Partners companies",
        "question": (
            "Which companies are under "
            "TNL Partners PLT?"
        ),
        "expected_intent": "auditor_companies",
        "expected_status": "success",
        "expected_auditor": (
            "TNL PARTNERS PLT"
        ),
        "expected_count": 4,
        "expected_result_contains": [
            {
                "Company Name": (
                    "CHARTERWAY REALTY SDN. BHD."
                ),
                "Auditor Name": (
                    "TNL PARTNERS PLT"
                ),
            },
        ],
    },

    {
        "name": "Hisham companies",
        "question": (
            "Which companies are under "
            "Hisham & Co?"
        ),
        "expected_intent": "auditor_companies",
        "expected_status": "success",
        "expected_auditor": (
            "HISHAM & CO"
        ),
        "expected_count": 2,
        "expected_result_contains": [
            {
                "Company Name": (
                    "FIRST TOUCH BOOKS & "
                    "STATIONERY SDN. BHD."
                ),
            },
            {
                "Company Name": (
                    "HOAY AUTOMATION SDN. BHD."
                ),
            },
        ],
    },

    {
        "name": "Distinct auditor list",
        "question": (
            "List all auditors"
        ),
        "expected_intent": "auditor_list",
        "expected_status": "success",
        "expected_auditor": "",
        "expected_count": 13,
        "expected_sources": [
            "auditors.db:Sheet1",
        ],
        "expected_unique_result_field": (
            "Auditor Name"
        ),
        "expected_result_sum": {
            "field": "Company Count",
            "value": 80,
        },
        "expected_result_contains": [
            {
                "Auditor Name": (
                    "Y.H.CHANG & PARTNERS"
                ),
                "Company Count": 35,
            },
            {
                "Auditor Name": (
                    "THELYX MALAYSIA"
                ),
                "Company Count": 1,
            },
            {
                "Auditor Name": (
                    "THELYX MALAYSIA PLT"
                ),
                "Company Count": 1,
            },
        ],
    },

    {
        "name": "Client company-name list",
        "question": (
            "List all company names"
        ),
        "expected_intent": "company_list",
        "expected_status": "success",
        "expected_count": 80,
        "expected_sources": [
            "Client_Master",
        ],
        "expected_unique_result_field": (
            "Company Name"
        ),
        "expected_result_keys": [
            "Company Name",
        ],
        "expected_sorted_result_field": (
            "Company Name"
        ),
        "expected_result_contains": [
            {
                "Company Name": (
                    "HIGHSCORE TRADING SDN. BHD."
                ),
            },
        ],
        "expected_result_excludes": [
            {
                "Company Name": (
                    "HIGHSCORE ESTATE SDN. BHD."
                ),
            },
        ],
    },

    {
        "name": "Show all client companies",
        "question": (
            "Show all companies"
        ),
        "expected_intent": "company_list",
        "expected_status": "success",
        "expected_count": 80,
        "expected_sources": [
            "Client_Master",
        ],
    },

    {
        "name": "Company-list spelling correction",
        "question": (
            "List all the comapnies"
        ),
        "expected_intent": "company_list",
        "expected_status": "success",
        "expected_count": 80,
        "expected_sources": [
            "Client_Master",
        ],
    },

    {
        "name": "All company annual-return dates",
        "question": (
            "List all companies' annual return dates"
        ),
        "expected_intent": "company_annual_return",
        "expected_status": "success",
        "expected_all_records": True,
        "expected_count": 80,
        "expected_sources": [
            "Client_Master",
        ],
        "expected_result_keys": [
            "Company Name",
            "Annual Return Date",
        ],
        "expected_nonempty_field_counts": {
            "Annual Return Date": 73,
        },
        "expected_sorted_result_field": (
            "Company Name"
        ),
        "expected_result_contains": [
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "Annual Return Date": "04/11/2025",
            },
        ],
        "expected_no_nan": True,
    },

    {
        "name": "Annual-return spelling correction",
        "question": (
            "list action multiple annual retrun date"
        ),
        "expected_intent": "company_annual_return",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_all_records": False,
        "expected_count": 1,
        "expected_sources": [
            "Client_Master",
        ],
        "expected_result_keys": [
            "Company Name",
            "Annual Return Date",
        ],
        "expected_result_contains": [
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "Annual Return Date": "04/11/2025",
            },
        ],
    },

    {
        "name": "Annual spelling correction",
        "question": (
            "show Action Multiple anual return date"
        ),
        "expected_intent": "company_annual_return",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_count": 1,
        "expected_result_contains": [
            {
                "Annual Return Date": "04/11/2025",
            },
        ],
    },

    {
        "name": "Company incorporation-date typo",
        "question": (
            "list ACtion Multiple incoperation date"
        ),
        "expected_intent": "company_information",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_all_records": False,
        "expected_company_fields": (
            "Incorporate Date",
        ),
        "expected_count": 1,
        "expected_sources": [
            "Client_Master",
        ],
        "expected_result_keys": [
            "Company Name",
            "Incorporate Date",
        ],
        "expected_result_contains": [
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "Incorporate Date": "",
            },
        ],
    },

    {
        "name": "Company incorporation date",
        "question": (
            "What is Affluence Capital's "
            "incorporation date?"
        ),
        "expected_intent": "company_information",
        "expected_status": "success",
        "expected_company": (
            "AFFLUENCE CAPITAL HOLDINGS SDN. BHD."
        ),
        "expected_company_fields": (
            "Incorporate Date",
        ),
        "expected_count": 1,
        "expected_result_contains": [
            {
                "Incorporate Date": "21/06/2022",
            },
        ],
    },

    {
        "name": "All company incorporation dates",
        "question": (
            "List all companies incorporation date"
        ),
        "expected_intent": "company_information",
        "expected_status": "success",
        "expected_all_records": True,
        "expected_company_fields": (
            "Incorporate Date",
        ),
        "expected_count": 80,
        "expected_result_keys": [
            "Company Name",
            "Incorporate Date",
        ],
        "expected_nonempty_field_counts": {
            "Incorporate Date": 40,
        },
        "expected_sorted_result_field": (
            "Company Name"
        ),
    },

    {
        "name": "Multiple company information fields",
        "question": (
            "Show Action Multiple business address "
            "and total issued shares"
        ),
        "expected_intent": "company_information",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_company_fields": (
            "Total Issued Shares",
            "Business Address",
        ),
        "expected_count": 1,
        "expected_result_keys": [
            "Company Name",
            "Total Issued Shares",
            "Business Address",
        ],
        "expected_result_contains": [
            {
                "Total Issued Shares": 50000,
            },
        ],
    },

    {
        "name": "Generic named-company details",
        "question": (
            "Show Action Multiple company details"
        ),
        "expected_intent": "company_data",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_count": 1,
        "expected_database_table": "Client_Master",
    },

    {
        "name": "Unknown company information safety",
        "question": (
            "Show NON EXISTENT TEST COMPANY "
            "incoperation date"
        ),
        "expected_intent": "company_information",
        "expected_status": "not_found",
        "expected_company": "",
        "expected_all_records": False,
        "expected_company_fields": (
            "Incorporate Date",
        ),
        "expected_count": 0,
    },

    {
        "name": "All complete company data",
        "question": "Show all company data",
        "expected_intent": "company_data",
        "expected_status": "success",
        "expected_all_records": True,
        "expected_count": 80,
        "expected_sources": [
            "Client_Master",
        ],
        "expected_database_table": "Client_Master",
        "expected_sorted_result_field": (
            "Company Name"
        ),
        "expected_result_contains": [
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "Annual Return Date": "04/11/2025",
                "Total Issued Shares": 50000,
            },
        ],
        "expected_no_nan": True,
    },

    {
        "name": "Complete data for one company",
        "question": (
            "Show complete company data for "
            "Action Multiple"
        ),
        "expected_intent": "company_data",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_all_records": False,
        "expected_count": 1,
        "expected_database_table": "Client_Master",
        "expected_no_nan": True,
    },

    {
        "name": "All extraction issues",
        "question": "List all extraction issues",
        "expected_intent": (
            "company_extraction_issues"
        ),
        "expected_status": "success",
        "expected_all_records": True,
        "expected_count": 426,
        "expected_sources": [
            "Extraction_Issues",
        ],
        "expected_database_table": (
            "Extraction_Issues"
        ),
        "expected_no_nan": True,
    },

    {
        "name": "Company extraction issues",
        "question": (
            "Show extraction issues for Action Multiple"
        ),
        "expected_intent": (
            "company_extraction_issues"
        ),
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_all_records": False,
        "expected_count": 10,
        "expected_database_table": (
            "Extraction_Issues"
        ),
        "expected_no_nan": True,
    },

    {
        "name": "All statutory documents",
        "question": "List all statutory documents",
        "expected_intent": (
            "company_statutory_documents"
        ),
        "expected_status": "success",
        "expected_all_records": True,
        "expected_count": 7496,
        "expected_sources": [
            "Statutory_Documents",
        ],
        "expected_database_table": (
            "Statutory_Documents"
        ),
        "expected_result_field_types": {
            "ParsedJSON": "str",
        },
        "expected_no_nan": True,
    },

    {
        "name": "Company statutory documents",
        "question": (
            "Show statutory documents for Action Multiple"
        ),
        "expected_intent": (
            "company_statutory_documents"
        ),
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_all_records": False,
        "expected_count": 165,
        "expected_database_table": (
            "Statutory_Documents"
        ),
        "expected_no_nan": True,
    },

    {
        "name": "All statutory events",
        "question": "List all statutory events",
        "expected_intent": (
            "company_statutory_events"
        ),
        "expected_status": "success",
        "expected_all_records": True,
        "expected_count": 821,
        "expected_sources": [
            "Statutory_Events",
        ],
        "expected_database_table": (
            "Statutory_Events"
        ),
        "expected_result_field_types": {
            "PayloadJSON": "str",
        },
        "expected_no_nan": True,
    },

    {
        "name": "Company statutory events",
        "question": (
            "Show statutory events for Action Multiple"
        ),
        "expected_intent": (
            "company_statutory_events"
        ),
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_all_records": False,
        "expected_count": 10,
        "expected_database_table": (
            "Statutory_Events"
        ),
        "expected_no_nan": True,
    },

    {
        "name": "All directors",
        "question": "List all directors",
        "expected_intent": "director_list",
        "expected_status": "success",
        "expected_all_records": True,
        "expected_count": 143,
        "expected_sources": [
            "Client_Master",
        ],
        "expected_result_keys": (
            DIRECTOR_RECORD_KEYS
        ),
        "expected_result_contains": [
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "Name": "KHOR PENG CHAI",
                "Race": "CHINESE",
                "Gender": "MALE",
            },
        ],
        "expected_no_nan": True,
    },

    {
        "name": "All shareholders",
        "question": "List all shareholders",
        "expected_intent": "shareholder_list",
        "expected_status": "success",
        "expected_all_records": True,
        "expected_count": 165,
        "expected_sources": [
            "Client_Master",
        ],
        "expected_result_keys": (
            SHAREHOLDER_RECORD_KEYS
        ),
        "expected_result_contains": [
            {
                "Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "Name": "LEE MOI TIANG",
                "Shares": 50000,
                "Analysis": (
                    "CITIZENS WHO ARE NON - MALAYS "
                    "AND NON- NATIVES"
                ),
            },
        ],
        "expected_no_nan": True,
    },

    {
        "name": "All current beneficial owners",
        "question": "List all beneficial owners",
        "expected_intent": "beneficial_owner_list",
        "expected_status": "success",
        "expected_all_records": True,
        "expected_count": 116,
        "expected_sources": [
            "EBOS_Master",
        ],
        "expected_result_contains": [
            {
                "Master Company Name": (
                    "ACTION MULTIPLE SDN. BHD."
                ),
                "Name": "LEE MOI TIANG",
                "Direct Ownership %": "100.0000",
            },
        ],
        "expected_no_nan": True,
    },

    {
        "name": "All auditor company records",
        "question": "List all auditor company records",
        "expected_intent": "auditor_company_list",
        "expected_status": "success",
        "expected_all_records": True,
        "expected_count": 80,
        "expected_sources": [
            "auditors.db:Sheet1",
        ],
        "expected_result_keys": (
            AUDITOR_RECORD_KEYS
        ),
        "expected_sorted_result_field": (
            "Company Name"
        ),
        "expected_no_nan": True,
    },

    {
        "name": "Unknown raw dataset company safety",
        "question": (
            "Show statutory documents for "
            "NON EXISTENT TEST COMPANY"
        ),
        "expected_intent": (
            "company_statutory_documents"
        ),
        "expected_status": "not_found",
        "expected_company": "",
        "expected_all_records": False,
        "expected_count": 0,
    },

    {
        "name": "Auditor companies spelling correction",
        "question": (
            "Which comapnies are under "
            "Y.H.CHANG & PARTNERS?"
        ),
        "expected_intent": "auditor_companies",
        "expected_status": "success",
        "expected_auditor": (
            "Y.H.CHANG & PARTNERS"
        ),
        "expected_count": 35,
        "expected_sources": [
            "auditors.db:Sheet1",
        ],
    },

    {
        "name": "Ambiguous auditor safety test",
        "question": (
            "Which companies are under Thelyx?"
        ),
        "expected_intent": "auditor_companies",
        "expected_status": "not_found",
        "expected_auditor": "",
        "expected_count": 0,
    },

    {
        "name": "Unknown auditor safety test",
        "question": (
            "Which companies are audited by "
            "NON EXISTENT AUDITOR?"
        ),
        "expected_intent": "auditor_companies",
        "expected_status": "not_found",
        "expected_auditor": "",
        "expected_count": 0,
    },

    {
        "name": "Unknown auditor company safety test",
        "question": (
            "Who is the auditor of "
            "NON EXISTENT TEST COMPANY SDN BHD?"
        ),
        "expected_intent": "auditor",
        "expected_status": "not_found",
        "expected_company": "",
        "expected_auditor": "",
        "expected_count": 0,
    },

    {
        "name": (
            "General company-secretarial knowledge"
        ),
        "question": (
            "How to transfer shares?"
        ),
        "expected_intent": "knowledge",
        "expected_status": "delegate",
        "expected_count": 0,
    },

    {
        "name": "Another general knowledge question",
        "question": (
            "What is the role of a company "
            "secretary in Malaysia?"
        ),
        "expected_intent": "knowledge",
        "expected_status": "delegate",
        "expected_count": 0,
    },

    {
        "name": "Unknown company safety test",
        "question": (
            "Who are the directors of "
            "NON EXISTENT TEST COMPANY SDN BHD?"
        ),
        "expected_intent": "director",
        "expected_status": "not_found",
        "expected_company": "",
        "expected_count": 0,
    },

    {
        "name": "Unknown person role safety test",
        "question": (
            "Show NON EXISTENT PERSON director, "
            "BO and shareholder status"
        ),
        "expected_intent": "person_status",
        "expected_status": "not_found",
        "expected_person": "",
        "expected_count": 0,
    },

    {
        "name": "Unknown directional person safety test",
        "question": (
            "NON EXISTENT PERSON is director of "
            "what company?"
        ),
        "expected_intent": "person_directorship",
        "expected_status": "not_found",
        "expected_person": "",
        "expected_count": 0,
    },

    {
        "name": "Two database scalar information",
        "question": (
            "What are the annual return date and "
            "financial year end date of ACTION "
            "MULTIPLE SDN BHD?"
        ),
        "expected_intent": "multi_intent",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_count": 2,
        "expected_section_count": 2,
        "expected_sources": [
            "csai_master.db:Client_Master",
            "auditors.db:Sheet1",
        ],
        "expected_sections": [
            {
                "intent": "company_information",
                "requested_fields": [
                    "Annual Return Date",
                ],
                "status": "success",
                "count": 1,
                "sources": [
                    "csai_master.db:Client_Master",
                ],
                "result_contains": [
                    {
                        "Company Name": (
                            "ACTION MULTIPLE SDN. BHD."
                        ),
                        "Annual Return Date": "04/11/2025",
                    },
                ],
            },
            {
                "intent": "auditor_information",
                "requested_fields": [
                    "Financial Year End",
                ],
                "status": "success",
                "count": 1,
                "sources": [
                    "auditors.db:Sheet1",
                ],
                "result_contains": [
                    {
                        "Financial Year End": "31 OCTOBER",
                    },
                ],
            },
        ],
    },

    {
        "name": "Directors and beneficial owners",
        "question": (
            "Who are the directors and beneficial owners "
            "of ACTION MULTIPLE SDN BHD?"
        ),
        "expected_intent": "multi_intent",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_count": 4,
        "expected_section_count": 2,
        "expected_sources": [
            "csai_master.db:Client_Master",
            "ebos_master.db:EBOS_Master",
        ],
        "expected_sections": [
            {
                "intent": "director",
                "count": 3,
                "result_contains": [
                    {"Name": "KHOR PENG CHAI"},
                ],
            },
            {
                "intent": "beneficial_owner",
                "count": 1,
                "result_contains": [
                    {"Name": "LEE MOI TIANG"},
                ],
            },
        ],
    },

    {
        "name": "Three database company query",
        "question": (
            "Show the directors, beneficial owners and "
            "auditor of ACTION MULTIPLE SDN BHD."
        ),
        "expected_intent": "multi_intent",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_count": 5,
        "expected_section_count": 3,
        "expected_sources": [
            "csai_master.db:Client_Master",
            "ebos_master.db:EBOS_Master",
            "auditors.db:Sheet1",
        ],
        "expected_sections": [
            {"intent": "director", "count": 3},
            {"intent": "beneficial_owner", "count": 1},
            {
                "intent": "auditor_information",
                "count": 1,
                "result_contains": [
                    {
                        "Auditor Name": (
                            "Y.H.CHANG & PARTNERS"
                        ),
                    },
                ],
            },
        ],
    },

    {
        "name": "Four relationship sections",
        "question": (
            "Show the directors, shareholders, beneficial "
            "owners and auditor of ACTION MULTIPLE SDN "
            "BHD."
        ),
        "expected_intent": "multi_intent",
        "expected_status": "success",
        "expected_count": 6,
        "expected_section_count": 4,
        "expected_sources": [
            "csai_master.db:Client_Master",
            "ebos_master.db:EBOS_Master",
            "auditors.db:Sheet1",
        ],
        "expected_sections": [
            {"intent": "director", "count": 3},
            {"intent": "shareholder", "count": 1},
            {"intent": "beneficial_owner", "count": 1},
            {"intent": "auditor_information", "count": 1},
        ],
    },

    {
        "name": "All four databases",
        "question": (
            "Show annual return date, financial year end "
            "date, beneficial owners, director written "
            "resolution and member written resolution of "
            "ACTION MULTIPLE SDN BHD."
        ),
        "expected_intent": "multi_intent",
        "expected_status": "success",
        "expected_count": 4,
        "expected_section_count": 4,
        "expected_sources": [
            "csai_master.db:Client_Master",
            "auditors.db:Sheet1",
            "ebos_master.db:EBOS_Master",
            "constitutions.db:Sheet1",
        ],
        "expected_sections": [
            {"intent": "company_information", "count": 1},
            {"intent": "auditor_information", "count": 1},
            {"intent": "beneficial_owner", "count": 1},
            {
                "intent": "constitution_information",
                "requested_fields": [
                    (
                        "DIRECTOR WRITTEN RESOLUTION "
                        "(DWR Statutory)"
                    ),
                    (
                        "MEMBER WRITTEN RESOLUTION "
                        "(MWR Statutory)"
                    ),
                ],
                "count": 1,
                "nonempty_result_fields": [
                    (
                        "DIRECTOR WRITTEN RESOLUTION "
                        "(DWR Statutory)"
                    ),
                    (
                        "MEMBER WRITTEN RESOLUTION "
                        "(MWR Statutory)"
                    ),
                ],
            },
        ],
    },

    {
        "name": "All-company multi-database query",
        "question": (
            "list all company names with annual return "
            "date and Financial Year end date"
        ),
        "expected_intent": "multi_intent",
        "expected_status": "success",
        "expected_all_records": True,
        "expected_count": 160,
        "expected_section_count": 2,
        "expected_sources": [
            "csai_master.db:Client_Master",
            "auditors.db:Sheet1",
        ],
        "expected_sections": [
            {
                "intent": "company_information",
                "count": 80,
                "requested_fields": [
                    "Annual Return Date",
                ],
            },
            {
                "intent": "auditor_information",
                "count": 80,
                "requested_fields": [
                    "Financial Year End",
                ],
            },
        ],
    },

    {
        "name": "Partial multi-database result",
        "question": (
            "Show the annual return date and beneficial "
            "owners of BENUA JASA SDN BHD."
        ),
        "expected_intent": "multi_intent",
        "expected_status": "partial_success",
        "expected_count": 1,
        "expected_section_count": 2,
        "expected_sources": [
            "csai_master.db:Client_Master",
            "ebos_master.db:EBOS_Master",
        ],
        "expected_sections": [
            {
                "intent": "company_information",
                "status": "success",
                "count": 1,
            },
            {
                "intent": "beneficial_owner",
                "status": "not_found",
                "count": 0,
                "sources": [
                    "ebos_master.db:EBOS_Master",
                ],
            },
        ],
    },

    {
        "name": "Single constitution query",
        "question": (
            "Show the DWR of ACTION MULTIPLE SDN BHD."
        ),
        "expected_intent": "constitution_information",
        "expected_status": "success",
        "expected_company": (
            "ACTION MULTIPLE SDN. BHD."
        ),
        "expected_count": 1,
        "expected_sources": [
            "constitutions.db:Sheet1",
        ],
        "expected_nonempty_result_fields": [
            (
                "DIRECTOR WRITTEN RESOLUTION "
                "(DWR Statutory)"
            ),
        ],
    },
]


def result_to_dict(result):

    if is_dataclass(result):

        return asdict(
            result
        )

    if isinstance(result, dict):

        return result

    return {
        "raw_result": result
    }


def record_matches(
    actual_record,
    expected_record
):

    for key, expected_value in expected_record.items():

        actual_value = actual_record.get(
            key
        )

        if actual_value != expected_value:

            return False

    return True


def run_checks(
    test_case,
    intent,
    result
):

    errors = []

    result_data = result_to_dict(
        result
    )

    expected_intent = test_case.get(
        "expected_intent"
    )

    if (
        expected_intent is not None
        and intent.intent != expected_intent
    ):

        errors.append(
            (
                f"Expected intent "
                f"'{expected_intent}', "
                f"received '{intent.intent}'."
            )
        )

    expected_status = test_case.get(
        "expected_status"
    )

    actual_status = result_data.get(
        "status",
        ""
    )

    if (
        expected_status is not None
        and actual_status != expected_status
    ):

        errors.append(
            (
                f"Expected status "
                f"'{expected_status}', "
                f"received '{actual_status}'."
            )
        )

    expected_company = test_case.get(
        "expected_company"
    )

    if expected_company is not None:

        actual_company = (
            getattr(
                intent,
                "company",
                ""
            )
            or ""
        )

        if actual_company != expected_company:

            errors.append(
                (
                    f"Expected company "
                    f"'{expected_company}', "
                    f"received '{actual_company}'."
                )
            )

    expected_person = test_case.get(
        "expected_person"
    )

    if expected_person is not None:

        actual_person = (
            getattr(
                intent,
                "person",
                ""
            )
            or ""
        )

        if actual_person != expected_person:

            errors.append(
                (
                    f"Expected person "
                    f"'{expected_person}', "
                    f"received '{actual_person}'."
                )
            )

    expected_all_records = test_case.get(
        "expected_all_records"
    )

    if expected_all_records is not None:

        actual_all_records = bool(
            getattr(
                intent,
                "all_records",
                False
            )
        )

        if actual_all_records != expected_all_records:

            errors.append(
                (
                    "Expected all_records to be "
                    f"{expected_all_records}, received "
                    f"{actual_all_records}."
                )
            )

    expected_company_fields = test_case.get(
        "expected_company_fields"
    )

    if expected_company_fields is not None:

        actual_company_fields = tuple(
            getattr(
                intent,
                "company_fields",
                ()
            )
            or ()
        )

        if actual_company_fields != expected_company_fields:

            errors.append(
                (
                    "Expected company fields "
                    f"{expected_company_fields}, received "
                    f"{actual_company_fields}."
                )
            )

    expected_auditor = test_case.get(
        "expected_auditor"
    )

    if expected_auditor is not None:

        actual_auditor = (
            result_data.get(
                "auditor",
                ""
            )
            or ""
        )

        if actual_auditor != expected_auditor:

            errors.append(
                (
                    f"Expected auditor "
                    f"'{expected_auditor}', "
                    f"received '{actual_auditor}'."
                )
            )

    expected_financial_year_end = test_case.get(
        "expected_financial_year_end"
    )

    if expected_financial_year_end is not None:

        actual_financial_year_end = (
            result_data.get(
                "financial_year_end",
                ""
            )
            or ""
        )

        if (
            actual_financial_year_end
            != expected_financial_year_end
        ):

            errors.append(
                (
                    "Expected financial year end "
                    f"'{expected_financial_year_end}', "
                    "received "
                    f"'{actual_financial_year_end}'."
                )
            )

    expected_count = test_case.get(
        "expected_count"
    )

    actual_count = result_data.get(
        "count",
        0
    )

    if (
        expected_count is not None
        and actual_count != expected_count
    ):

        errors.append(
            (
                f"Expected exactly "
                f"{expected_count} result(s), "
                f"received {actual_count}."
            )
        )

    expected_records = test_case.get(
        "expected_result_contains",
        []
    )

    actual_records = result_data.get(
        "results",
        []
    ) or []

    for expected_record in expected_records:

        found = any(
            record_matches(
                actual_record,
                expected_record
            )
            for actual_record in actual_records
        )

        if not found:

            errors.append(
                (
                    "Expected result record "
                    f"was not found: "
                    f"{expected_record}"
                )
            )

    excluded_records = test_case.get(
        "expected_result_excludes",
        []
    )

    for excluded_record in excluded_records:

        found = any(
            record_matches(
                actual_record,
                excluded_record
            )
            for actual_record in actual_records
        )

        if found:

            errors.append(
                (
                    "Excluded result record "
                    f"was found: "
                    f"{excluded_record}"
                )
            )

    expected_result_keys = test_case.get(
        "expected_result_keys"
    )

    if expected_result_keys is not None:

        expected_keys = set(
            expected_result_keys
        )

        for actual_record in actual_records:

            if set(actual_record) != expected_keys:

                errors.append(
                    (
                        "Expected every result record "
                        f"to contain only "
                        f"{expected_result_keys}."
                    )
                )

                break

    expected_database_table = test_case.get(
        "expected_database_table"
    )

    if expected_database_table:

        expected_keys = set(
            database_columns(
                expected_database_table
            )
        )

        for actual_record in actual_records:

            if set(actual_record) != expected_keys:

                errors.append(
                    (
                        "Expected every result record "
                        "to match the columns in "
                        f"{expected_database_table}."
                    )
                )

                break

    nonempty_fields = test_case.get(
        "expected_nonempty_result_fields",
        []
    )

    for field in nonempty_fields:

        empty_record_count = sum(
            1
            for record in actual_records
            if record.get(field) in (
                None,
                ""
            )
        )

        if empty_record_count:

            errors.append(
                (
                    "Expected every result record "
                    f"to contain a nonempty '{field}' "
                    f"value; {empty_record_count} "
                    "record(s) did not."
                )
            )

    nonempty_field_counts = test_case.get(
        "expected_nonempty_field_counts",
        {}
    )

    for field, expected_value in (
        nonempty_field_counts.items()
    ):

        actual_value = sum(
            1
            for record in actual_records
            if record.get(field) not in (None, "")
        )

        if actual_value != expected_value:

            errors.append(
                (
                    f"Expected {expected_value} nonempty "
                    f"'{field}' value(s), received "
                    f"{actual_value}."
                )
            )

    expected_field_types = test_case.get(
        "expected_result_field_types",
        {}
    )

    for field, expected_type in (
        expected_field_types.items()
    ):

        wrong_type_count = sum(
            1
            for record in actual_records
            if type(record.get(field)).__name__
            != expected_type
        )

        if wrong_type_count:

            errors.append(
                (
                    f"Expected every '{field}' value to "
                    f"have type {expected_type}; "
                    f"{wrong_type_count} record(s) did not."
                )
            )

    if (
        test_case.get("expected_no_nan")
        and contains_nan(actual_records)
    ):

        errors.append(
            "Expected results not to contain NaN values."
        )

    sorted_field = test_case.get(
        "expected_sorted_result_field"
    )

    if sorted_field:

        values = [
            record.get(
                sorted_field
            )
            for record in actual_records
        ]

        expected_values = sorted(
            values,
            key=lambda value: (
                str(value).upper(),
                str(value)
            )
        )

        if values != expected_values:

            errors.append(
                (
                    "Expected result values to be "
                    f"sorted by '{sorted_field}'."
                )
            )

    expected_sources = test_case.get(
        "expected_sources"
    )

    if expected_sources is not None:

        actual_sources = result_data.get(
            "sources",
            []
        ) or []

        if actual_sources != expected_sources:

            errors.append(
                (
                    "Expected sources "
                    f"{expected_sources}, "
                    f"received {actual_sources}."
                )
            )

    expected_section_count = test_case.get(
        "expected_section_count"
    )
    actual_sections = result_data.get(
        "sections",
        [],
    ) or []

    if (
        expected_section_count is not None
        and len(actual_sections) != expected_section_count
    ):
        errors.append(
            (
                "Expected exactly "
                f"{expected_section_count} section(s), "
                f"received {len(actual_sections)}."
            )
        )

    expected_sections = test_case.get(
        "expected_sections",
        [],
    )

    for index, expected_section in enumerate(
        expected_sections
    ):

        if index >= len(actual_sections):
            errors.append(
                (
                    "Expected section was not found at "
                    f"position {index + 1}: "
                    f"{expected_section.get('intent', '')}."
                )
            )
            continue

        actual_section = actual_sections[index]

        for expected_key in (
            "intent",
            "requested_fields",
            "status",
            "count",
            "sources",
        ):

            if expected_key not in expected_section:
                continue

            if (
                actual_section.get(expected_key)
                != expected_section[expected_key]
            ):
                errors.append(
                    (
                        f"Section {index + 1} expected "
                        f"{expected_key}="
                        f"{expected_section[expected_key]}, "
                        "received "
                        f"{actual_section.get(expected_key)}."
                    )
                )

        section_records = actual_section.get(
            "results",
            [],
        ) or []

        for expected_record in expected_section.get(
            "result_contains",
            [],
        ):

            if not any(
                record_matches(record, expected_record)
                for record in section_records
            ):
                errors.append(
                    (
                        f"Section {index + 1} did not "
                        "contain expected record: "
                        f"{expected_record}."
                    )
                )

        for field in expected_section.get(
            "nonempty_result_fields",
            [],
        ):

            if not section_records or any(
                record.get(field) in (None, "")
                for record in section_records
            ):
                errors.append(
                    (
                        f"Section {index + 1} expected "
                        f"nonempty field '{field}'."
                    )
                )

    unique_field = test_case.get(
        "expected_unique_result_field"
    )

    if unique_field:

        values = [
            record.get(
                unique_field
            )

            for record in actual_records
        ]

        if len(values) != len(set(values)):

            errors.append(
                (
                    "Expected unique result values "
                    f"for '{unique_field}'."
                )
            )

    expected_sum = test_case.get(
        "expected_result_sum"
    )

    if expected_sum:

        field = expected_sum[
            "field"
        ]

        expected_value = expected_sum[
            "value"
        ]

        actual_value = sum(
            record.get(
                field,
                0
            )
            or 0

            for record in actual_records
        )

        if actual_value != expected_value:

            errors.append(
                (
                    f"Expected '{field}' to sum "
                    f"to {expected_value}, "
                    f"received {actual_value}."
                )
            )

    expected_field_counts = test_case.get(
        "expected_result_field_counts"
    )

    if expected_field_counts:

        field = expected_field_counts[
            "field"
        ]

        for value, expected_value in (
            expected_field_counts[
                "values"
            ].items()
        ):

            actual_value = sum(
                1
                for record in actual_records
                if record.get(field) == value
            )

            if actual_value != expected_value:

                errors.append(
                    (
                        f"Expected {expected_value} "
                        f"record(s) where '{field}' "
                        f"is '{value}', received "
                        f"{actual_value}."
                    )
                )

    return errors


def main():

    router = Router()
    service = CSAIService()

    passed = 0
    failed = 0

    try:

        for index, test_case in enumerate(
            TEST_CASES,
            start=1
        ):

            print()
            print("=" * 100)

            print(
                f"TEST {index}: "
                f"{test_case['name']}"
            )

            print("=" * 100)

            question = test_case[
                "question"
            ]

            print(
                "Question:",
                question
            )

            intent = router.detect(
                question
            )

            print(
                "Detected intent:",
                intent
            )

            result = service.execute(
                intent
            )

            result_data = result_to_dict(
                result
            )

            print("Result:")

            display_data = dict(
                result_data
            )

            display_results = (
                display_data.get(
                    "results",
                    []
                )
                or []
            )

            if len(display_results) > 10:

                display_data["results"] = [
                    *display_results[:3],
                    {
                        "...": (
                            f"{len(display_results) - 3} "
                            "additional record(s)"
                        )
                    },
                ]

            print(display_data)

            errors = run_checks(
                test_case,
                intent,
                result
            )

            if errors:

                failed += 1

                print()
                print(
                    "TEST STATUS: FAILED"
                )

                for error in errors:

                    print(
                        "-",
                        error
                    )

            else:

                passed += 1

                print()
                print(
                    "TEST STATUS: PASSED"
                )

    finally:

        service.close()

        print()
        print("=" * 100)
        print(
            "CSAI resources closed successfully."
        )

    print()
    print("=" * 100)
    print("TEST SUMMARY")
    print("=" * 100)

    print(
        "Passed:",
        passed
    )

    print(
        "Failed:",
        failed
    )

    print(
        "Total:",
        passed + failed
    )

    return 0 if failed == 0 else 1


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
