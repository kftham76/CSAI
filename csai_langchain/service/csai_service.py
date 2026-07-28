from csai_langchain.domain.responses import SearchResult

from csai_langchain.tools.director_tool import DirectorTool
from csai_langchain.tools.shareholder_tool import ShareholderTool
from csai_langchain.tools.beneficial_owner_tool import (
    BeneficialOwnerTool,
)
from csai_langchain.tools.person_directorship_tool import (
    PersonDirectorshipTool,
)


class CSAIService:

    def __init__(self):

        self.director_tool = DirectorTool()
        self.shareholder_tool = ShareholderTool()
        self.bo_tool = BeneficialOwnerTool()
        self.person_tool = PersonDirectorshipTool()

        self._closed = False

    ####################################################
    # Missing entity responses
    ####################################################

    @staticmethod
    def missing_company_result(intent_name):

        return SearchResult(
            status="not_found",
            intent=intent_name,
            answer=(
                "The company could not be matched "
                "to a company in the client database."
            ),
            company="",
            person="",
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

    ####################################################
    # Main entry point
    ####################################################

    def execute(self, intent):

        if self._closed:

            raise RuntimeError(
                "CSAIService has already been closed."
            )

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

        question = (
            getattr(
                intent,
                "question",
                ""
            )
            or ""
        ).strip()

        ################################################
        # Director
        ################################################

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