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