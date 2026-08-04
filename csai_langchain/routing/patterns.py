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

AUDITOR_COMPANY_LIST = [

    re.compile(
        r"\b(?:all|every|each)\b.*"
        r"\bauditor\b.*"
        r"\b(?:data|records?)\b",
        re.I
    ),

    re.compile(
        r"\b(?:all|every|each)\b.*"
        r"\bcompan(?:y|ies)\b.*"
        r"\bauditors?\b",
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

FINANCIAL_YEAR_END = [

    re.compile(
        r"\bfinancial"
        r"(?:\s*-\s*|\s+)"
        r"year"
        r"(?:\s*-\s*|\s+)"
        r"end\b",
        re.I
    ),

    re.compile(
        r"\bfye\b",
        re.I
    ),
]

ANNUAL_RETURN = [

    re.compile(
        r"\bann?ual\s+"
        r"ret(?:ur|ru)ns?\b",
        re.I
    ),

    re.compile(
        r"\bar\s+dates?\b",
        re.I
    ),
]

COMPANY_DATA = [

    re.compile(
        r"\b(?:all|complete|full)\b.*"
        r"\b(?:company|client)\b.*"
        r"\b(?:data|records?)\b",
        re.I
    ),

    re.compile(
        r"\bclient\s+master\b",
        re.I
    ),
]

COMPANY_INFORMATION = [

    re.compile(
        r"\b(?:company\s+)?"
        r"(?:information|info|details|profile)\b",
        re.I
    ),

    re.compile(
        r"\btell\s+me\s+about\b",
        re.I
    ),
]

EXTRACTION_ISSUES = [

    re.compile(
        r"\bextraction\s+"
        r"(?:issues?|errors?|warnings?)\b",
        re.I
    ),
]

STATUTORY_DOCUMENTS = [

    re.compile(
        r"\bstatutory\s+documents?\b",
        re.I
    ),
]

STATUTORY_EVENTS = [

    re.compile(
        r"\bstatutory\s+events?\b",
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
        r"\bebos\b",
        re.I
    ),

    re.compile(
        r"\bbo\b",
        re.I
    ),
]

PERSON_DIRECTORSHIP = [

    re.compile(
        r"\b(?:list|show|display|provide|get)\b"
        r".*\bcompan(?:y|ies)\b"
        r".*\bdirectors?\b",
        re.I
    ),

    re.compile(
        r"appointed as director",
        re.I
    ),

    re.compile(
        r"\b(?:which|what)\s+compan(?:y|ies)\b"
        r".*\bdirectors?\b",
        re.I
    ),

    re.compile(
        r"\bdirectors?\b"
        r".*\b(?:which|what)\s+compan(?:y|ies)\b",
        re.I
    ),

    re.compile(
        r"directorship",
        re.I
    ),
]

PERSON_STATUS = [

    re.compile(
        r"(?=.*\b(?:directors?|directorship)\b)"
        r"(?=.*\b(?:bo|beneficial\s+owners?)\b)"
        r"(?=.*\b(?:shareholders?|members?)\b)",
        re.I
    ),
]

PERSON_BENEFICIAL_OWNERSHIP = [

    re.compile(
        r"\b(?:list|show|display|provide|get)\b"
        r".*\bcompan(?:y|ies)\b"
        r".*\b(?:bo|beneficial\s+"
        r"(?:owners?|ownership))\b",
        re.I
    ),

    re.compile(
        r"\b(?:which|what)\s+compan(?:y|ies)\b"
        r".*\b(?:bo|beneficial\s+"
        r"(?:owners?|ownership))\b",
        re.I
    ),

    re.compile(
        r"\b(?:bo|beneficial\s+"
        r"(?:owners?|ownership))\b"
        r".*\b(?:which|what)\s+compan(?:y|ies)\b",
        re.I
    ),

    re.compile(
        r"\b(?:bo|beneficial\s+ownership)\b"
        r".*\b(?:history|status)\b",
        re.I
    ),

    re.compile(
        r"\b(?:history|status)\b"
        r".*\b(?:bo|beneficial\s+ownership)\b",
        re.I
    ),
]

PERSON_SHAREHOLDING = [

    re.compile(
        r"\b(?:list|show|display|provide|get)\b"
        r".*\bcompan(?:y|ies)\b"
        r".*\b(?:sharehold(?:ers?|ing)|members?)\b",
        re.I
    ),

    re.compile(
        r"\b(?:which|what)\s+compan(?:y|ies)\b"
        r".*\b(?:sharehold(?:ers?|ing)|members?)\b",
        re.I
    ),

    re.compile(
        r"\b(?:sharehold(?:ers?|ing)|members?)\b"
        r".*\b(?:which|what)\s+compan(?:y|ies)\b",
        re.I
    ),

    re.compile(
        r"\b(?:shareholding|shareholder|member)\b"
        r".*\b(?:history|status)\b",
        re.I
    ),

    re.compile(
        r"\b(?:history|status)\b"
        r".*\b(?:shareholding|shareholder|member)\b",
        re.I
    ),
]
