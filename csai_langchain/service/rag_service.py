from csai_langchain.domain.responses import (
    SearchResult,
)

from csai_langchain.rag.chain import (
    RAGChain,
)


class RAGService:

    def __init__(
        self,
        collection_name=None
    ):

        self.collection_name = (
            collection_name
            or ""
        ).strip()

        self.chain = None
        self._closed = False

    def _get_chain(self):

        if not self.collection_name:

            raise RuntimeError(
                "Document RAG is not configured. "
                "General knowledge should be delegated "
                "to Hermes."
            )

        if self.chain is None:

            self.chain = RAGChain(
                collection_name=self.collection_name
            )

        return self.chain

    def ask(
        self,
        question
    ):

        if self._closed:

            raise RuntimeError(
                "RAGService has already been closed."
            )

        chain = self._get_chain()

        result = chain.run(
            question
        )

        return SearchResult(
            status=result["status"],
            intent="knowledge",
            answer=result["answer"],
            company="",
            person="",
            count=0,
            results=[],
            sources=result.get(
                "sources",
                []
            )
        )

    def close(self):

        if self._closed:
            return

        if self.chain is not None:

            chain = self.chain
            self.chain = None

            chain.close()

        self._closed = True