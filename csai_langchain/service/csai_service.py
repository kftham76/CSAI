from csai_langchain.domain.intent import MultiIntent
from csai_langchain.domain.responses import (
    MultiSearchResult,
    SearchResult,
    SearchSection,
)
from csai_langchain.routing.capabilities import (
    INTENT_SOURCES,
)

from csai_langchain.tools.director_tool import DirectorTool
from csai_langchain.tools.shareholder_tool import ShareholderTool
from csai_langchain.tools.beneficial_owner_tool import (
    BeneficialOwnerTool,
)
from csai_langchain.tools.person_directorship_tool import (
    PersonDirectorshipTool,
)
from csai_langchain.tools.auditor_tool import AuditorTool
from csai_langchain.tools.company_list_tool import (
    CompanyListTool,
)
from csai_langchain.tools.person_status_tool import (
    PersonStatusTool,
)
from csai_langchain.tools.constitution_tool import (
    ConstitutionTool,
)


class CSAIService:

    def __init__(self):

        self.director_tool = DirectorTool()
        self.shareholder_tool = ShareholderTool()
        self.bo_tool = BeneficialOwnerTool()
        self.person_tool = PersonDirectorshipTool()
        self.auditor_tool = AuditorTool()
        self.company_list_tool = CompanyListTool()
        self.person_status_tool = PersonStatusTool()
        self.constitution_tool = ConstitutionTool()

        self._closed = False

    ####################################################
    # Missing entity responses
    ####################################################

    @staticmethod
    def missing_company_result(
        intent_name,
        database_name="client database"
    ):

        return SearchResult(
            status="not_found",
            intent=intent_name,
            answer=(
                "The company could not be matched "
                f"to a company in the {database_name}."
            ),
            company="",
            person="",
            count=0,
            results=[],
            sources=[]
        )

    @staticmethod
    def missing_auditor_result(intent_name):

        return SearchResult(
            status="not_found",
            intent=intent_name,
            answer=(
                "The auditor could not be matched "
                "to an auditor in the auditor database."
            ),
            company="",
            person="",
            auditor="",
            count=0,
            results=[],
            sources=[]
        )

    @staticmethod
    def missing_financial_year_end_result(
        intent_name
    ):

        return SearchResult(
            status="not_found",
            intent=intent_name,
            answer=(
                "The financial year end could not be "
                "identified. Provide a month or a day "
                "and month."
            ),
            financial_year_end="",
            count=0,
            results=[],
            sources=[]
        )

    @staticmethod
    def missing_person_result(intent_name):

        return SearchResult(
            status="not_found",
            intent=intent_name,
            answer=(
                "The person could not be matched "
                "to a person in the client database."
            ),
            company="",
            person="",
            count=0,
            results=[],
            sources=[]
        )

    @staticmethod
    def missing_all_records_result(intent_name):

        return SearchResult(
            status="not_found",
            intent=intent_name,
            answer=(
                "An explicit request for all records "
                "is required."
            ),
            count=0,
            results=[],
            sources=[]
        )

    ####################################################
    # Main entry point
    ####################################################

    @staticmethod
    def _result_value(result, name, default=None):

        if isinstance(result, dict):
            return result.get(name, default)

        return getattr(result, name, default)

    def _execute_multi(self, multi_intent):

        sections = []
        sources = []

        for child_intent in multi_intent.intents:

            intent_name = child_intent.intent
            source = INTENT_SOURCES.get(
                intent_name,
                "",
            )
            section_sources = [source] if source else []

            for item in section_sources:
                if item not in sources:
                    sources.append(item)

            requested_fields = list(
                child_intent.requested_fields
                or child_intent.company_fields
                or ()
            )

            try:
                result = self.execute(child_intent)
                section = SearchSection(
                    intent=intent_name,
                    requested_fields=requested_fields,
                    status=self._result_value(
                        result,
                        "status",
                        "error",
                    ),
                    answer=self._result_value(
                        result,
                        "answer",
                        "",
                    ),
                    count=int(
                        self._result_value(
                            result,
                            "count",
                            0,
                        )
                        or 0
                    ),
                    results=list(
                        self._result_value(
                            result,
                            "results",
                            [],
                        )
                        or []
                    ),
                    # Multi results always report the exact
                    # database and table, including misses.
                    sources=section_sources,
                )
            except Exception as error:
                section = SearchSection(
                    intent=intent_name,
                    requested_fields=requested_fields,
                    status="error",
                    answer=str(error),
                    count=0,
                    results=[],
                    sources=section_sources,
                )

            sections.append(section)

        statuses = [section.status for section in sections]
        successful = sum(
            status == "success"
            for status in statuses
        )

        if sections and successful == len(sections):
            status = "success"
            answer = ""
        elif successful:
            status = "partial_success"
            answer = (
                "Some requested information could not "
                "be retrieved."
            )
        elif any(item == "error" for item in statuses):
            status = "error"
            answer = (
                "The requested information could not "
                "be retrieved."
            )
        else:
            status = "not_found"
            answer = "No requested information was found."

        return MultiSearchResult(
            status=status,
            answer=answer,
            company=multi_intent.company,
            count=sum(
                section.count for section in sections
            ),
            section_count=len(sections),
            sections=sections,
            sources=sources,
        )

    def execute(self, intent):

        if self._closed:

            raise RuntimeError(
                "CSAIService has already been closed."
            )

        if isinstance(intent, MultiIntent):
            return self._execute_multi(intent)

        intent_name = (
            getattr(
                intent,
                "intent",
                ""
            )
            or ""
        ).strip()

        company = (
            getattr(
                intent,
                "company",
                ""
            )
            or ""
        ).strip()

        person = (
            getattr(
                intent,
                "person",
                ""
            )
            or ""
        ).strip()

        auditor = (
            getattr(
                intent,
                "auditor",
                ""
            )
            or ""
        ).strip()

        financial_year_end = (
            getattr(
                intent,
                "financial_year_end",
                ""
            )
            or ""
        ).strip()

        all_records = bool(
            getattr(
                intent,
                "all_records",
                False
            )
        )

        company_fields = tuple(
            getattr(
                intent,
                "company_fields",
                ()
            )
            or ()
        )

        question = (
            getattr(
                intent,
                "question",
                ""
            )
            or ""
        ).strip()

        ################################################
        # Complete Client_Master company records
        ################################################

        if intent_name == "company_data":

            if not company and not all_records:
                return self.missing_company_result(
                    "company_data"
                )

            results = (
                self.company_list_tool
                .get_all_company_records()
                if all_records
                else self.company_list_tool
                .get_company_records(company)
            )

            return SearchResult(
                status=(
                    "success" if results else "not_found"
                ),
                intent="company_data",
                answer=(
                    "" if results
                    else "No company data was found."
                ),
                company=company,
                count=len(results),
                results=results,
                sources=(
                    ["Client_Master"] if results else []
                )
            )

        ################################################
        # Annual-return dates
        ################################################

        if intent_name == "company_annual_return":

            if not company and not all_records:
                return self.missing_company_result(
                    "company_annual_return"
                )

            results = (
                self.company_list_tool
                .get_all_annual_return_dates()
                if all_records
                else self.company_list_tool
                .get_annual_return_date(company)
            )

            return SearchResult(
                status=(
                    "success" if results else "not_found"
                ),
                intent="company_annual_return",
                answer=(
                    "" if results
                    else "No annual-return data was found."
                ),
                company=company,
                count=len(results),
                results=results,
                sources=(
                    ["Client_Master"] if results else []
                )
            )

        ################################################
        # Requested Client_Master information fields
        ################################################

        if intent_name == "company_information":

            if not company_fields:
                return SearchResult(
                    status="not_found",
                    intent="company_information",
                    answer=(
                        "No supported company information "
                        "field was identified."
                    ),
                    company=company,
                    count=0,
                    results=[],
                    sources=[]
                )

            if not company and not all_records:
                return self.missing_company_result(
                    "company_information"
                )

            results = (
                self.company_list_tool
                .get_all_company_information(
                    company_fields
                )
                if all_records
                else self.company_list_tool
                .get_company_information(
                    company,
                    company_fields
                )
            )

            return SearchResult(
                status=(
                    "success" if results else "not_found"
                ),
                intent="company_information",
                answer=(
                    "" if results
                    else "No company information was found."
                ),
                company=company,
                count=len(results),
                results=results,
                sources=(
                    ["Client_Master"] if results else []
                )
            )

        ################################################
        # Requested auditor database fields
        ################################################

        if intent_name == "auditor_information":

            requested_fields = tuple(
                getattr(
                    intent,
                    "requested_fields",
                    (),
                )
                or ()
            )

            if not requested_fields:
                return SearchResult(
                    status="not_found",
                    intent="auditor_information",
                    answer=(
                        "No supported auditor field was "
                        "identified."
                    ),
                    company=company,
                    count=0,
                    results=[],
                    sources=[],
                )

            if not company and not all_records:
                return self.missing_company_result(
                    "auditor_information",
                    "auditor database",
                )

            results = (
                self.auditor_tool
                .get_all_company_information(
                    requested_fields
                )
                if all_records
                else self.auditor_tool
                .get_company_information(
                    company,
                    requested_fields,
                )
            )

            return SearchResult(
                status=(
                    "success" if results else "not_found"
                ),
                intent="auditor_information",
                answer=(
                    ""
                    if results
                    else "No auditor information was found."
                ),
                company=company,
                count=len(results),
                results=results,
                sources=(
                    ["auditors.db:Sheet1"]
                    if results
                    else []
                ),
            )

        ################################################
        # Requested constitution database fields
        ################################################

        if intent_name == "constitution_information":

            requested_fields = tuple(
                getattr(
                    intent,
                    "requested_fields",
                    (),
                )
                or ()
            )

            if not requested_fields:
                return SearchResult(
                    status="not_found",
                    intent="constitution_information",
                    answer=(
                        "No supported constitution field "
                        "was identified."
                    ),
                    company=company,
                    count=0,
                    results=[],
                    sources=[],
                )

            if not company and not all_records:
                return self.missing_company_result(
                    "constitution_information",
                    "constitution database",
                )

            results = (
                self.constitution_tool
                .get_all_company_information(
                    requested_fields
                )
                if all_records
                else self.constitution_tool
                .get_company_information(
                    company,
                    requested_fields,
                )
            )

            return SearchResult(
                status=(
                    "success" if results else "not_found"
                ),
                intent="constitution_information",
                answer=(
                    ""
                    if results
                    else (
                        "No constitution information "
                        "was found."
                    )
                ),
                company=company,
                count=len(results),
                results=results,
                sources=(
                    ["constitutions.db:Sheet1"]
                    if results
                    else []
                ),
            )

        ################################################
        # Raw csai_master operational datasets
        ################################################

        raw_datasets = {
            "company_extraction_issues": (
                "Extraction_Issues",
                self.company_list_tool
                .get_all_extraction_issues,
                self.company_list_tool
                .get_extraction_issues_for_company,
            ),
            "company_statutory_documents": (
                "Statutory_Documents",
                self.company_list_tool
                .get_all_statutory_documents,
                self.company_list_tool
                .get_statutory_documents_for_company,
            ),
            "company_statutory_events": (
                "Statutory_Events",
                self.company_list_tool
                .get_all_statutory_events,
                self.company_list_tool
                .get_statutory_events_for_company,
            ),
        }

        if intent_name in raw_datasets:

            if not company and not all_records:
                return self.missing_company_result(
                    intent_name
                )

            (
                source_name,
                get_all_records,
                get_company_records,
            ) = raw_datasets[intent_name]

            results = (
                get_all_records()
                if all_records
                else get_company_records(company)
            )

            return SearchResult(
                status=(
                    "success" if results else "not_found"
                ),
                intent=intent_name,
                answer=(
                    "" if results
                    else "No matching records were found."
                ),
                company=company,
                count=len(results),
                results=results,
                sources=(
                    [source_name] if results else []
                )
            )

        ################################################
        # Person beneficial-ownership history
        ################################################

        if (
            intent_name
            == "person_beneficial_ownership"
        ):

            if not person:

                return self.missing_person_result(
                    "person_beneficial_ownership"
                )

            results = (
                self.person_status_tool
                .get_beneficial_ownership_history(
                    person
                )
            )

            return SearchResult(
                status=(
                    "success"
                    if results
                    else "not_found"
                ),
                intent=(
                    "person_beneficial_ownership"
                ),
                answer=(
                    (
                        f"{person} has "
                        f"{len(results)} "
                        "beneficial-ownership "
                        "history event(s)."
                    )
                    if results
                    else (
                        "No beneficial-ownership "
                        "history was found for "
                        f"{person}."
                    )
                ),
                company="",
                person=person,
                auditor="",
                count=len(results),
                results=results,
                sources=(
                    [
                        "EBOS_Master"
                    ]
                    if results
                    else []
                )
            )

        ################################################
        # Person shareholding
        ################################################

        if intent_name == "person_shareholding":

            if not person:

                return self.missing_person_result(
                    "person_shareholding"
                )

            results = (
                self.person_status_tool
                .get_company_associations(
                    person
                )
            )

            return SearchResult(
                status=(
                    "success"
                    if results
                    else "not_found"
                ),
                intent="person_shareholding",
                answer=(
                    (
                        f"{person} has current director "
                        "or shareholder associations "
                        "with "
                        f"{len(results)} "
                        "company(ies)."
                    )
                    if results
                    else (
                        "No current director or "
                        "shareholder associations "
                        "were found for "
                        f"{person}."
                    )
                ),
                company="",
                person=person,
                auditor="",
                count=len(results),
                results=results,
                sources=(
                    [
                        "Client_Master"
                    ]
                    if results
                    else []
                )
            )

        ################################################
        # Combined person relationship status
        ################################################

        if intent_name == "person_status":

            if not person:

                return self.missing_person_result(
                    "person_status"
                )

            results = (
                self.person_status_tool
                .get_combined_status(
                    person
                )
            )

            return SearchResult(
                status=(
                    "success"
                    if results
                    else "not_found"
                ),
                intent="person_status",
                answer=(
                    (
                        f"{len(results)} director, "
                        "beneficial-owner, and "
                        "shareholder record(s) "
                        f"were found for {person}."
                    )
                    if results
                    else (
                        "No director, beneficial-owner, "
                        "or shareholder records were "
                        f"found for {person}."
                    )
                ),
                company="",
                person=person,
                auditor="",
                count=len(results),
                results=results,
                sources=(
                    [
                        "Client_Master",
                        "EBOS_Master",
                    ]
                    if results
                    else []
                )
            )

        ################################################
        # Financial year end to companies
        ################################################

        if intent_name == "auditor_company_list":

            if not all_records:
                return self.missing_all_records_result(
                    "auditor_company_list"
                )

            results = (
                self.auditor_tool
                .get_all_company_records()
            )

            return SearchResult(
                status=(
                    "success" if results else "not_found"
                ),
                intent="auditor_company_list",
                answer=(
                    "" if results
                    else "No auditor company records were found."
                ),
                count=len(results),
                results=results,
                sources=(
                    ["auditors.db:Sheet1"]
                    if results
                    else []
                )
            )

        if (
            intent_name
            == "auditor_financial_year_end"
        ):

            if not financial_year_end:

                return (
                    self
                    .missing_financial_year_end_result(
                        "auditor_financial_year_end"
                    )
                )

            if financial_year_end == "ALL":

                results = (
                    self.auditor_tool
                    .get_all_company_records()
                )

            else:

                results = (
                    self.auditor_tool
                    .get_companies_by_financial_year_end(
                        financial_year_end
                    )
                )

            return SearchResult(
                status=(
                    "success"
                    if results
                    else "not_found"
                ),
                intent=(
                    "auditor_financial_year_end"
                ),
                answer=(
                    ""
                    if results
                    else (
                        "No auditor company records "
                        "were found."
                    )
                ),
                financial_year_end=(
                    financial_year_end
                ),
                count=len(results),
                results=results,
                sources=(
                    [
                        "auditors.db:Sheet1"
                    ]
                    if results
                    else []
                )
            )

        ################################################
        # Company to auditor
        ################################################

        if intent_name == "auditor":

            if not company:

                return self.missing_company_result(
                    "auditor",
                    "auditor database"
                )

            results = (
                self.auditor_tool
                .get_auditor_for_company(
                    company
                )
            )

            resolved_auditor = (
                results[0].get(
                    "Auditor Name",
                    ""
                )
                if results
                else ""
            )
            resolved_financial_year_end = (
                results[0].get(
                    "Financial Year End",
                    ""
                )
                if results
                else ""
            )

            return SearchResult(
                status=(
                    "success"
                    if results
                    else "not_found"
                ),
                intent="auditor",
                answer=(
                    ""
                    if results
                    else "No auditor was found."
                ),
                company=company,
                person="",
                auditor=resolved_auditor,
                financial_year_end=(
                    resolved_financial_year_end
                ),
                count=len(results),
                results=results,
                sources=(
                    [
                        "auditors.db:Sheet1"
                    ]
                    if results
                    else []
                )
            )

        ################################################
        # Auditor to companies
        ################################################

        if intent_name == "auditor_companies":

            if not auditor:

                return self.missing_auditor_result(
                    "auditor_companies"
                )

            results = (
                self.auditor_tool
                .get_companies_by_auditor(
                    auditor
                )
            )

            return SearchResult(
                status=(
                    "success"
                    if results
                    else "not_found"
                ),
                intent="auditor_companies",
                answer=(
                    ""
                    if results
                    else (
                        "No companies were found "
                        "for this auditor."
                    )
                ),
                company="",
                person="",
                auditor=auditor,
                count=len(results),
                results=results,
                sources=(
                    [
                        "auditors.db:Sheet1"
                    ]
                    if results
                    else []
                )
            )

        ################################################
        # Distinct auditor list
        ################################################

        if intent_name == "auditor_list":

            results = (
                self.auditor_tool
                .get_distinct_auditors()
            )

            return SearchResult(
                status=(
                    "success"
                    if results
                    else "not_found"
                ),
                intent="auditor_list",
                answer=(
                    ""
                    if results
                    else "No auditors were found."
                ),
                company="",
                person="",
                auditor="",
                count=len(results),
                results=results,
                sources=(
                    [
                        "auditors.db:Sheet1"
                    ]
                    if results
                    else []
                )
            )

        ################################################
        # Client company-name list
        ################################################

        if intent_name == "company_list":

            results = (
                self.company_list_tool
                .get_all_company_names()
            )

            return SearchResult(
                status=(
                    "success"
                    if results
                    else "not_found"
                ),
                intent="company_list",
                answer=(
                    ""
                    if results
                    else "No companies were found."
                ),
                company="",
                person="",
                auditor="",
                count=len(results),
                results=results,
                sources=(
                    [
                        "Client_Master"
                    ]
                    if results
                    else []
                )
            )

        ################################################
        # Director
        ################################################

        if intent_name == "director_list":

            if not all_records:
                return self.missing_all_records_result(
                    "director_list"
                )

            results = (
                self.director_tool
                .get_all_directors()
            )

            return SearchResult(
                status=(
                    "success" if results else "not_found"
                ),
                intent="director_list",
                answer=(
                    "" if results
                    else "No directors were found."
                ),
                count=len(results),
                results=results,
                sources=(
                    ["Client_Master"] if results else []
                )
            )

        if intent_name == "shareholder_list":

            if not all_records:
                return self.missing_all_records_result(
                    "shareholder_list"
                )

            results = (
                self.shareholder_tool
                .get_all_shareholders()
            )

            return SearchResult(
                status=(
                    "success" if results else "not_found"
                ),
                intent="shareholder_list",
                answer=(
                    "" if results
                    else "No shareholders were found."
                ),
                count=len(results),
                results=results,
                sources=(
                    ["Client_Master"] if results else []
                )
            )

        if intent_name == "beneficial_owner_list":

            if not all_records:
                return self.missing_all_records_result(
                    "beneficial_owner_list"
                )

            results = (
                self.bo_tool
                .get_all_current_beneficial_owners()
            )

            return SearchResult(
                status=(
                    "success" if results else "not_found"
                ),
                intent="beneficial_owner_list",
                answer=(
                    "" if results
                    else "No current beneficial owners were found."
                ),
                count=len(results),
                results=results,
                sources=(
                    ["EBOS_Master"] if results else []
                )
            )

        if intent_name == "director":

            if not company:

                return self.missing_company_result(
                    "director"
                )

            results = self.director_tool.execute(
                company
            )

            return SearchResult(
                status=(
                    "success"
                    if results
                    else "not_found"
                ),
                intent="director",
                answer=(
                    ""
                    if results
                    else "No directors were found."
                ),
                company=company,
                person="",
                count=len(results),
                results=results,
                sources=[
                    "Client_Master"
                ]
            )

        ################################################
        # Shareholder
        ################################################

        if intent_name == "shareholder":

            if not company:

                return self.missing_company_result(
                    "shareholder"
                )

            results = self.shareholder_tool.execute(
                company
            )

            return SearchResult(
                status=(
                    "success"
                    if results
                    else "not_found"
                ),
                intent="shareholder",
                answer=(
                    ""
                    if results
                    else "No shareholders were found."
                ),
                company=company,
                person="",
                count=len(results),
                results=results,
                sources=[
                    "Client_Master"
                ]
            )

        ################################################
        # Beneficial owner
        ################################################

        if intent_name == "beneficial_owner":

            if not company:

                return self.missing_company_result(
                    "beneficial_owner"
                )

            results = self.bo_tool.execute(
                company
            )

            return SearchResult(
                status=(
                    "success"
                    if results
                    else "not_found"
                ),
                intent="beneficial_owner",
                answer=(
                    ""
                    if results
                    else (
                        "No current beneficial owners "
                        "were found."
                    )
                ),
                company=company,
                person="",
                count=len(results),
                results=results,
                sources=[
                    "EBOS_Master"
                ]
            )

        ################################################
        # Person directorship
        ################################################

        if intent_name == "person_directorship":

            if not person:

                return self.missing_person_result(
                    "person_directorship"
                )

            results = self.person_tool.execute(
                person
            )

            return SearchResult(
                status=(
                    "success"
                    if results
                    else "not_found"
                ),
                intent="person_directorship",
                answer=(
                    (
                        f"{person} is appointed as director "
                        f"in {len(results)} companies."
                    )
                    if results
                    else (
                        "No directorship records were found "
                        f"for {person}."
                    )
                ),
                company="",
                person=person,
                count=len(results),
                results=results,
                sources=[
                    "Client_Master"
                ]
            )

        ################################################
# Delegate general conversation to Agent Layer
################################################

        if intent_name in {
            "knowledge",
            "greeting",
        }:

            return SearchResult(
                status="delegate",
                intent=intent_name,
                answer="",
                company="",
                person="",
                count=0,
                results=[],
                sources=[]
            )

        ################################################
        # Unknown intent
        ################################################

        return SearchResult(
            status="error",
            intent=intent_name,
            answer="Unknown intent.",
            company=company,
            person=person,
            auditor=auditor,
            count=0,
            results=[],
            sources=[]
        )

    ####################################################
# Close
####################################################

    def close(self):

        if self._closed:
            return

        # Structured repositories open and close their
        # own SQLite connections per request.
        self._closed = True
