from dataclasses import asdict, is_dataclass

from csai_langchain.routing.router import Router
from csai_langchain.service.csai_service import CSAIService


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
                "Shares": "50000",
                "Share Type": "ORDINARY SHARES",
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
                "Direct Ownership %": "100.0000",
                "Voting Shares %": "100.0000",
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
            },
        ],
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
            print(result_data)

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
