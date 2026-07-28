import re

DIRECTOR = [

    re.compile(
        r"\bdirectors?\b",
        re.I
    ),

    re.compile(
        r"who are the directors",
        re.I
    ),
]

SHAREHOLDER = [

    re.compile(
        r"\bshareholders?\b",
        re.I
    ),

    re.compile(
        r"list shareholders",
        re.I
    ),
]

BENEFICIAL_OWNER = [

    re.compile(
        r"beneficial owner",
        re.I
    ),

    re.compile(
        r"\bbo\b",
        re.I
    ),
]

PERSON_DIRECTORSHIP = [

    re.compile(
        r"appointed as director",
        re.I
    ),

    re.compile(
        r"companies?.*director",
        re.I
    ),

    re.compile(
        r"director.*companies?",
        re.I
    ),

    re.compile(
        r"directorship",
        re.I
    ),
]