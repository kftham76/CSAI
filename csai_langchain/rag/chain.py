from langchain_ollama import ChatOllama

from csai_langchain.config.settings import (
    OLLAMA_URL,
    LLM_MODEL,
    SIMILARITY_THRESHOLD,
)

from csai_langchain.rag.prompt import PROMPT
from csai_langchain.rag.retriever import Retriever


MAX_CONTEXT = 4000
MAX_CHUNK_LENGTH = 1500


class RAGChain:

    def __init__(
        self,
        collection_name
    ):

        self.retriever = Retriever(
            collection_name=collection_name
        )

        self.llm = ChatOllama(
            model=LLM_MODEL,
            base_url=OLLAMA_URL,
            temperature=0
        )

        self._closed = False

    def run(
        self,
        question
    ):

        if self._closed:

            raise RuntimeError(
                "RAGChain has already been closed."
            )

        question = (
            question
            or ""
        ).strip()

        if not question:

            return {
                "status": "error",
                "answer": "Please provide a valid question.",
                "sources": []
            }

        results = self.retriever.search(
            question
        )

        relevant_results = [
            result
            for result in results
            if float(
                result.get(
                    "score",
                    0
                )
            ) >= SIMILARITY_THRESHOLD
        ]

        if not relevant_results:

            return {
                "status": "not_found",
                "answer": (
                    "Information not found "
                    "in the configured knowledge collection."
                ),
                "sources": []
            }

        context_parts = []
        sources = []

        for result in relevant_results:

            text = (
                result.get(
                    "text",
                    ""
                )
                or ""
            ).strip()

            if text:

                context_parts.append(
                    text[:MAX_CHUNK_LENGTH]
                )

            payload = (
                result.get(
                    "payload",
                    {}
                )
                or {}
            )

            source = (
                payload.get("source")
                or payload.get("file")
                or payload.get("filename")
                or payload.get("Source PDF")
            )

            if (
                source
                and source not in sources
            ):

                sources.append(
                    source
                )

        context = "\n\n".join(
            context_parts
        )[:MAX_CONTEXT]

        if not context:

            return {
                "status": "not_found",
                "answer": (
                    "Information not found "
                    "in the configured knowledge collection."
                ),
                "sources": []
            }

        prompt = PROMPT.format(
            context=context,
            question=question
        )

        response = self.llm.invoke(
            prompt
        )

        answer = (
            getattr(
                response,
                "content",
                ""
            )
            or ""
        ).strip()

        return {
            "status": (
                "success"
                if answer
                else "error"
            ),
            "answer": (
                answer
                or "The model returned an empty answer."
            ),
            "sources": sources
        }

    def close(self):

        if self._closed:
            return

        self.retriever.close()
        self._closed = True