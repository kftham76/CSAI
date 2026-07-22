from .ebos_company_tools import (
    get_ebos_company
)


from datetime import datetime

from .ebos_company_tools import (
    get_ebos_company
)


def parse_date(d):

    try:
        return datetime.strptime(
            d,
            "%d/%m/%Y"
        )
    except:
        return datetime.min


def get_shareholders(company_name):

    rows = get_ebos_company(
        company_name
    )

    latest = {}

    for row in rows:

        name = str(
            row.get(
                "Name",
                ""
            )
        ).strip()

        if not name:
            continue

        key = (
            row.get("IC")
            or name
        )

        filing_date = max(

            parse_date(
                row.get(
                    "Date of Data Recorded",
                    ""
                )
            ),

            parse_date(
                row.get(
                    "Date Received",
                    ""
                )
            ),

            parse_date(
                row.get(
                    "PDF Date",
                    ""
                )
            )
        )

        old = latest.get(key)

        if (
            old is None
            or
            filing_date >
            old["_date"]
        ):

            latest[key] = {

                "_date":
                    filing_date,

                "Name":
                    name,

                "IC":
                    row.get(
                        "IC"
                    ),

                "Nationality":
                    row.get(
                        "Nationality"
                    ),

                "Designation":
                    row.get(
                        "Designation"
                    ),

                "BO Status":
                    row.get(
                        "BO Status"
                    ),

                "Direct Ownership %":
                    row.get(
                        "Criteria A - Direct Ownership %",
                        ""
                    ),

                "Voting Shares %":
                    row.get(
                        "Criteria B - Voting Shares %",
                        ""
                    ),

                "Date of Becoming BO":
                    row.get(
                        "Date of Becoming BO"
                    ),

                "Date of Cessation":
                    row.get(
                        "Date of Cessation"
                    )
            }

    shareholders = []

    for v in latest.values():

        if (
            str(
                v["BO Status"]
            ).upper()
            ==
            "CESSATION"
        ):
            continue

        shareholders.append({

            k: val
            for k, val in v.items()
            if k != "_date"
        })

    return shareholders