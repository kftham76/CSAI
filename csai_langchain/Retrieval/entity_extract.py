import re


def extract_company(question):

    patterns = [

        r"directors of (.*)",
        r"shareholders of (.*)",
        r"company profile of (.*)",
        r"show company (.*)"
    ]

    q = question.lower()

    for p in patterns:

        m = re.search(
            p,
            q
        )

        if m:

            return (
                m.group(1)
                .strip()
                .upper()
            )

    return None


def extract_person(question):

    patterns = [

        r"which companies is (.*?) appointed",

        r"appointments of (.*)",

        r"companies of (.*)"
    ]

    q = question.lower()

    for p in patterns:

        m = re.search(
            p,
            q
        )

        if m:

            return (
                m.group(1)
                .strip()
                .upper()
            )

    return None