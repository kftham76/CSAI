import re

from .patterns import *
from .entity_extractor import EntityExtractor
from .capabilities import CAPABILITIES
from csai_langchain.domain.intent import Intent, MultiIntent


class Router:

    def __init__(self):
        self.extractor = EntityExtractor()

    @staticmethod
    def requests_all_records(question):

        return bool(
            re.search(
                r"\b(?:all|every|each)\b",
                question,
                re.I
            )
        )

    @staticmethod
    def _first_pattern_position(patterns, question):

        positions = [
            match.start()
            for pattern in patterns
            for match in [pattern.search(question)]
            if match
        ]

        return min(positions) if positions else None

    def _company_field_position(self, question, field):

        normalized_question = self.extractor.normalize(
            question
        )
        candidates = [
            alias
            for alias, column in (
                self.extractor.COMPANY_FIELD_ALIASES.items()
            )
            if column == field
        ]
        candidates.append(
            self.extractor.normalize(field)
        )
        positions = [
            normalized_question.find(candidate)
            for candidate in candidates
            if (
                candidate
                and normalized_question.find(candidate) >= 0
            )
        ]

        return (
            min(positions)
            if positions
            else len(normalized_question)
        )

    def _capability_requests(self, question):

        requests = []
        seen = set()
        complete_ebos_record_request = bool(
            re.search(
                r"\b(?:complete|full)\s+"
                r"(?:ebos?|beneficial\s+owners?)\s+"
                r"(?:data|records?|information)\b",
                question,
                re.I,
            )
        )

        for capability in CAPABILITIES:

            position = self._first_pattern_position(
                capability.patterns,
                question,
            )

            if position is None:
                continue

            identity = (
                capability.group,
                capability.requested_field,
            )

            if identity in seen:
                continue

            seen.add(identity)
            requests.append({
                "group": capability.group,
                "intent": capability.intent,
                "field": capability.requested_field,
                "position": position,
            })

        for field in (
            self.extractor.extract_company_fields(question)
        ):

            # Fields such as Business Address are also
            # part of complete EBOS records. Preserve the
            # legacy EBOS-only interpretation in that
            # explicit role-record context.
            if complete_ebos_record_request:
                continue

            identity = (
                "company_information",
                field,
            )

            if identity in seen:
                continue

            seen.add(identity)
            requests.append({
                "group": "company_information",
                "intent": "company_information",
                "field": field,
                "position": self._company_field_position(
                    question,
                    field,
                ),
            })

        return sorted(
            requests,
            key=lambda request: request["position"],
        )

    def _detect_multi_intent(
        self,
        question,
        normalized_question,
        requests_all,
    ):

        requests = self._capability_requests(question)

        groups = {}

        for request in requests:

            group = groups.setdefault(
                request["group"],
                {
                    "intent": request["intent"],
                    "position": request["position"],
                    "fields": [],
                },
            )

            if request["field"] not in group["fields"]:
                group["fields"].append(request["field"])

        # A single repository/result shape remains on the
        # legacy single-intent path. Compound routing starts
        # only when separate result sections are required.
        if len(groups) < 2:
            return None

        company = self.extractor.extract_company(question)
        person = self.extractor.extract_person(question)

        person_directional = any(
            pattern.search(normalized_question)
            for patterns in (
                PERSON_STATUS,
                PERSON_BENEFICIAL_OWNERSHIP,
                PERSON_SHAREHOLDING,
                PERSON_DIRECTORSHIP,
            )
            for pattern in patterns
        )

        legal_company_cue = bool(
            re.search(
                r"\b(?:sdn|bhd|berhad|limited|ltd)\b",
                normalized_question,
                re.I,
            )
        )
        relationship_company_cue = bool(
            re.search(
                r"\b(?:of|for)\b",
                normalized_question,
                re.I,
            )
            and not re.search(
                r"\b(?:history|status)\b",
                normalized_question,
                re.I,
            )
        )

        if (
            person
            and person_directional
            and not company
        ):
            return None

        if not (
            company
            or requests_all
            or legal_company_cue
            or relationship_company_cue
        ):
            return None

        all_records = bool(
            requests_all and not company
        )
        list_intents = {
            "director": "director_list",
            "shareholder": "shareholder_list",
            "beneficial_owner": (
                "beneficial_owner_list"
            ),
        }
        intents = []

        for _, group in sorted(
            groups.items(),
            key=lambda item: item[1]["position"],
        ):

            intent_name = group["intent"]

            if all_records:
                intent_name = list_intents.get(
                    intent_name,
                    intent_name,
                )

            fields = tuple(group["fields"])
            intents.append(
                Intent(
                    intent=intent_name,
                    company=company,
                    question=question,
                    all_records=all_records,
                    company_fields=(
                        fields
                        if intent_name
                        == "company_information"
                        else ()
                    ),
                    requested_fields=fields,
                )
            )

        return MultiIntent(
            intents=tuple(intents),
            company=company,
            question=question,
            all_records=all_records,
        )

    def detect(self, question):

        q = question.lower()

        # Correct only the observed company-word
        # transpositions used for intent routing. Keep
        # the original question in the returned Intent.
        q = re.sub(
            r"\bcomapnies\b",
            "companies",
            q
        )

        q = re.sub(
            r"\bcomapny\b",
            "company",
            q
        )

        requests_all = self.requests_all_records(
            q
        )

        multi_intent = self._detect_multi_intent(
            question,
            q,
            requests_all,
        )

        if multi_intent is not None:
            return multi_intent

        # combined person relationship status
        for p in PERSON_STATUS:
            if p.search(q):
                return Intent(
                    intent="person_status",
                    person=self.extractor.extract_person(
                        question
                    ),
                    question=question
                )

        # person beneficial-ownership history
        for p in PERSON_BENEFICIAL_OWNERSHIP:
            if p.search(q):

                person = self.extractor.extract_person(
                    question
                )

                if requests_all and not person:
                    break

                return Intent(
                    intent=(
                        "person_beneficial_ownership"
                    ),
                    person=person,
                    question=question
                )

        # person shareholding
        for p in PERSON_SHAREHOLDING:
            if p.search(q):

                person = self.extractor.extract_person(
                    question
                )

                if requests_all and not person:
                    break

                return Intent(
                    intent="person_shareholding",
                    person=person,
                    question=question
                )

        # person directorship
        for p in PERSON_DIRECTORSHIP:
            if p.search(q):

                person = self.extractor.extract_person(
                    question
                )

                if requests_all and not person:
                    break

                return Intent(
                    intent="person_directorship",
                    person=person,
                    question=question
                )

        # All auditor-company records must be checked
        # before the broader company-data patterns.
        for p in AUDITOR_COMPANY_LIST:
            if p.search(q):

                company = (
                    self.extractor
                    .extract_auditor_company(question)
                )

                if company:
                    return Intent(
                        intent="auditor",
                        company=company,
                        question=question
                    )

                return Intent(
                    intent="auditor_company_list",
                    all_records=True,
                    question=question
                )

        # Complete client-master records
        for p in COMPANY_DATA:
            if p.search(q):

                if re.search(
                    r"\b(?:"
                    r"auditors?|auditing|"
                    r"directors?|shareholders?|members?|"
                    r"beneficial\s+owners?|ebos|bo"
                    r")\b",
                    q,
                    re.I
                ):
                    break

                company = self.extractor.extract_company(
                    question
                )

                return Intent(
                    intent="company_data",
                    company=company,
                    all_records=(
                        requests_all and not company
                    ),
                    question=question
                )

        # Annual-return dates
        for p in ANNUAL_RETURN:
            if p.search(q):

                company = self.extractor.extract_company(
                    question
                )
                requested_company_fields = (
                    self.extractor
                    .extract_company_fields(question)
                )

                if len(requested_company_fields) > 1:
                    return Intent(
                        intent="company_information",
                        company=company,
                        all_records=(
                            requests_all and not company
                        ),
                        company_fields=(
                            requested_company_fields
                        ),
                        question=question,
                    )

                return Intent(
                    intent="company_annual_return",
                    company=company,
                    all_records=(
                        requests_all and not company
                    ),
                    question=question
                )

        # Requested Client_Master fields. Exact database
        # column names and common aliases are supported.
        company_fields = (
            self.extractor
            .extract_company_fields(question)
        )

        has_role_specific_term = bool(
            re.search(
                r"\b(?:"
                r"auditors?|auditing|"
                r"directors?|shareholders?|members?|"
                r"beneficial\s+owners?|ebos|bo"
                r")\b",
                q,
                re.I
            )
        )

        if company_fields and not has_role_specific_term:

            company = self.extractor.extract_company(
                question
            )

            is_company_name_list = (
                company_fields == ("Company Name",)
                and not company
                and any(
                    pattern.search(q)
                    for pattern in COMPANY_LIST
                )
            )

            if not is_company_name_list:
                return Intent(
                    intent="company_information",
                    company=company,
                    all_records=(
                        requests_all and not company
                    ),
                    company_fields=company_fields,
                    question=question
                )

        constitution_fields = tuple(
            request["field"]
            for request in self._capability_requests(
                question
            )
            if request["group"]
            == "constitution_information"
        )

        if constitution_fields:

            company = self.extractor.extract_company(
                question
            )

            return Intent(
                intent="constitution_information",
                company=company,
                all_records=(
                    requests_all and not company
                ),
                requested_fields=constitution_fields,
                question=question,
            )

        # Client extraction diagnostics
        for p in EXTRACTION_ISSUES:
            if p.search(q):

                company = self.extractor.extract_company(
                    question
                )

                return Intent(
                    intent="company_extraction_issues",
                    company=company,
                    all_records=(
                        requests_all and not company
                    ),
                    question=question
                )

        # Statutory source-document records
        for p in STATUTORY_DOCUMENTS:
            if p.search(q):

                company = self.extractor.extract_company(
                    question
                )

                return Intent(
                    intent="company_statutory_documents",
                    company=company,
                    all_records=(
                        requests_all and not company
                    ),
                    question=question
                )

        # Statutory event records
        for p in STATUTORY_EVENTS:
            if p.search(q):

                company = self.extractor.extract_company(
                    question
                )

                return Intent(
                    intent="company_statutory_events",
                    company=company,
                    all_records=(
                        requests_all and not company
                    ),
                    question=question
                )

        # company financial-year-end lookup or
        # reverse financial-year-end company lookup
        for p in FINANCIAL_YEAR_END:
            if p.search(q):

                company = (
                    self.extractor
                    .extract_auditor_company(
                        question
                    )
                )
                financial_year_end = (
                    self.extractor
                    .extract_financial_year_end(
                        question
                    )
                )

                if company:
                    return Intent(
                        intent="auditor",
                        company=company,
                        financial_year_end=(
                            financial_year_end
                        ),
                        question=question
                    )

                return Intent(
                    intent=(
                        "auditor_financial_year_end"
                    ),
                    financial_year_end=(
                        financial_year_end
                    ),
                    question=question
                )

        # distinct auditor list
        for p in AUDITOR_LIST:
            if p.search(q):

                company = (
                    self.extractor
                    .extract_auditor_company(
                        question
                    )
                )

                if company:
                    return Intent(
                        intent="auditor",
                        company=company,
                        question=question
                    )

                return Intent(
                    intent="auditor_list",
                    question=question
                )

        # recognized auditor firm
        auditor = self.extractor.extract_auditor(
            question
        )

        if auditor:
            return Intent(
                intent="auditor_companies",
                auditor=auditor,
                question=question
            )

        # reverse auditor lookup with an unknown firm
        for p in AUDITOR_COMPANIES:
            if p.search(q):
                return Intent(
                    intent="auditor_companies",
                    auditor="",
                    question=question
                )

        # company auditor lookup
        for p in AUDITOR:
            if p.search(q):
                return Intent(
                    intent="auditor",
                    company=(
                        self.extractor
                        .extract_auditor_company(
                            question
                        )
                    ),
                    question=question
                )

        # client company-name list
        for p in COMPANY_LIST:
            if p.search(q):
                return Intent(
                    intent="company_list",
                    question=question
                )

        # beneficial owner
        for p in BENEFICIAL_OWNER:
            if p.search(q):

                company = self.extractor.extract_company(
                    question
                )

                return Intent(
                    intent=(
                        "beneficial_owner_list"
                        if requests_all and not company
                        else "beneficial_owner"
                    ),
                    company=company,
                    all_records=(
                        requests_all and not company
                    ),
                    question=question
                )

        # shareholder
        for p in SHAREHOLDER:
            if p.search(q):

                company = self.extractor.extract_company(
                    question
                )

                return Intent(
                    intent=(
                        "shareholder_list"
                        if requests_all and not company
                        else "shareholder"
                    ),
                    company=company,
                    all_records=(
                        requests_all and not company
                    ),
                    question=question
                )

        # director
        for p in DIRECTOR:
            if p.search(q):

                company = self.extractor.extract_company(
                    question
                )

                return Intent(
                    intent=(
                        "director_list"
                        if requests_all and not company
                        else "director"
                    ),
                    company=company,
                    all_records=(
                        requests_all and not company
                    ),
                    question=question
                )

        # Generic information/details for a recognized
        # company return its complete Client_Master row.
        for p in COMPANY_INFORMATION:
            if p.search(q):

                company = self.extractor.extract_company(
                    question
                )

                return Intent(
                    intent="company_data",
                    company=company,
                    all_records=(
                        requests_all and not company
                    ),
                    question=question
                )

        return Intent(
            intent="knowledge",
            question=question
        )
