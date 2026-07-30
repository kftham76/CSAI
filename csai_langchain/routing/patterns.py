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

    ####################################################
    # Shareholder terminology
    ####################################################

    re.compile(
        r"\bshareholders?\b",
        re.I
    ),

    re.compile(
        r"\blist\s+"
        r"(?:me\s+)?"
        r"(?:the\s+)?"
        r"shareholders?\b",
        re.I
    ),

    ####################################################
    # Member terminology
    #
    # In company-registry questions, member/members
    # should be treated as shareholder/shareholders.
    ####################################################

    re.compile(
        r"\b"
        r"(?:list|show|give|display|provide|get)"
        r"\s+"
        r"(?:me\s+)?"
        r"(?:the\s+)?"
        r"(?:company\s+)?"
        r"members?"
        r"\b",
        re.I
    ),

    re.compile(
        r"\bwho\s+"
        r"(?:is|are)\s+"
        r"(?:the\s+)?"
        r"(?:company\s+)?"
        r"members?"
        r"\b",
        re.I
    ),

    re.compile(
        r"\b"
        r"(?:find|identify)\s+"
        r"(?:the\s+)?"
        r"(?:company\s+)?"
        r"members?"
        r"\b",
        re.I
    ),
]

AUDITOR_LIST = [

    re.compile(
        r"\b"
        r"(?:list|show|display|provide|get)"
        r"\s+"
        r"(?:me\s+)?"
        r"(?:all\s+)?"
        r"(?:the\s+)?"
        r"(?:auditors?|audit\s+firms?)"
        r"\b",
        re.I
    ),

    re.compile(
        r"\bwhat\s+"
        r"(?:are|is)\s+"
        r"(?:all\s+)?"
        r"(?:the\s+)?"
        r"(?:auditors?|audit\s+firms?)"
        r"\b",
        re.I
    ),
]

AUDITOR_COMPANIES = [

    re.compile(
        r"\bcompanies?\b.*"
        r"\b(?:under|audited\s+by)\b",
        re.I
    ),

    re.compile(
        r"\baudited\s+by\b",
        re.I
    ),
]

AUDITOR = [

    re.compile(
        r"\bauditors?\b",
        re.I
    ),

    re.compile(
        r"\baudit(?:ing)?\s+firms?\b",
        re.I
    ),

    re.compile(
        r"\bwho\s+audits\b",
        re.I
    ),
]

COMPANY_LIST = [

    re.compile(
        r"\b"
        r"(?:list|show|display|provide|get)"
        r"\s+"
        r"(?:me\s+)?"
        r"(?:all\s+)?"
        r"(?:the\s+)?"
        r"(?:client\s+)?"
        r"(?:company\s+names?|companies)"
        r"\b",
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
