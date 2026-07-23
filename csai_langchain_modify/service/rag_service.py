from csai_langchain_modify.domain.responses import SearchResult
from csai_langchain_modify.rag.chain import RAGChain


class RAGService:

    def __init__(self):

        self.chain = RAGChain()

    def ask(self, question):

        result = self.chain.run(
            question
        )

        return SearchResult(
            status=result["status"],
            intent="knowledge",
            answer=result["answer"],
            count=0,
            results=[],
            sources=result.get(
                "sources",
                []
            )
        )

    def close(self):

        self.chain.close()