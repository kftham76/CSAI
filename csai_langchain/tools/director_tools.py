import pandas as pd

from .company_tools import (
    get_company,
    get_all_companies
)


def get_directors(company_name):

    data = get_company(company_name)

    if not data:
        return []

    row = data[0]

    directors = []

    for i in range(1, 50):

        key = f"Director{i} Name"

        if key not in row:
            break

        name = row.get(key)

        if pd.isna(name):
            continue

        name = str(name).strip()

        if not name:
            continue

        directors.append({

            "Name": name,

            "IC":
                row.get(
                    f"Director{i} IC"
                ),

            "DOB":
                row.get(
                    f"Director{i} DOB"
                ),

            "Nationality":
                row.get(
                    f"Director{i} Nationality"
                ),

            "Residential Address":
                row.get(
                    f"Director{i} Residential Address"
                )
        })

    return directors


def get_person_directorship(person_name):

    person_name = (
        person_name
        .strip()
        .upper()
    )

    companies = get_all_companies()

    results = []

    for row in companies:

        for i in range(1, 50):

            key = f"Director{i} Name"

            if key not in row:
                break

            name = row.get(key)

            if pd.isna(name):
                continue

            name = (
                str(name)
                .strip()
                .upper()
            )

            if name == person_name:

                results.append({

                    "Company Name":
                        row.get(
                            "Company Name"
                        ),

                    "Company Reg No":
                        row.get(
                            "Company Reg No"
                        )
                })

                break

    return results