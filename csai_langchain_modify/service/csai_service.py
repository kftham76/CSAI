from csai_langchain_modify.domain.responses import SearchResult

from csai_langchain_modify.tools.director_tool import DirectorTool
from csai_langchain_modify.tools.shareholder_tool import ShareholderTool
from csai_langchain_modify.tools.beneficial_owner_tool import BeneficialOwnerTool
from csai_langchain_modify.tools.person_directorship_tool import PersonDirectorshipTool
from csai_langchain_modify.service.rag_service import RAGService

class CSAIService:

    def __init__(self):

        self.director_tool = DirectorTool()
        self.shareholder_tool = ShareholderTool()
        self.bo_tool = BeneficialOwnerTool()
        self.person_tool = PersonDirectorshipTool()
        self.rag_service = RAGService()

    ####################################################
    # Main Entry Point
    ####################################################

    def execute(self, intent):

        if intent.intent == "director":

            results = self.director_tool.execute(
                intent.company
            )

            return SearchResult(

                status="success",

                intent="director",

                company=intent.company,

                count=len(results),

                results=results
            )

        ################################################

        if intent.intent == "shareholder":

            results = self.shareholder_tool.execute(
                intent.company
            )

            return SearchResult(

                status="success",

                intent="shareholder",

                company=intent.company,

                count=len(results),

                results=results
            )

        ################################################

        if intent.intent == "beneficial_owner":

            results = self.bo_tool.execute(
                intent.company
            )

            return SearchResult(

                status="success",

                intent="beneficial_owner",

                company=intent.company,

                count=len(results),

                results=results
            )

        ################################################

        if intent.intent == "person_directorship":

            results = self.person_tool.execute(
                intent.person
            )

            return SearchResult(

                status="success",

                intent="person_directorship",

                person=intent.person,

                count=len(results),

                results=results,

                answer=(
                    f"{intent.person} is appointed as director "
                    f"in {len(results)} companies."
                )
            )

        ################################################

        if intent.intent == "knowledge":

            return self.rag_service.ask(
                intent.question
            )

        ################################################

        return SearchResult(

            status="error",

            intent=intent.intent,

            answer="Unknown intent.",

            results=[]
        )