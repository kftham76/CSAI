from langchain_ollama import ChatOllama

from csai_langchain_modify.config.settings import (
    OLLAMA_URL,
    LLM_MODEL,
    SIMILARITY_THRESHOLD,
)

from csai_langchain_modify.rag.prompt import PROMPT
from csai_langchain_modify.rag.retriever import Retriever


class RAGChain:

    def __init__(self):

        self.retriever = Retriever()

        self.llm = ChatOllama(
            model=LLM_MODEL,
            base_url=OLLAMA_URL,
            temperature=0
        )

    def run(self, question):

        results = self.retriever.search(
            question
        )

        if not results:

            return {
                "status": "not_found",
                "answer": (
                    "Information not found "
                    "in the knowledge base."
                ),
                "sources": []
            }

        top_score = results[0]["score"]

        print(
            "Top Score:",
            round(top_score, 4)
        )

        if top_score < SIMILARITY_THRESHOLD:

            return {
                "status": "not_found",
                "answer": (
                    "Information not found "
                    "in the knowledge base."
                ),
                "sources": []
            }

        context_parts = []
        sources = []

        for result in results:

            text = result["text"]

            context_parts.append(
                text[:1500]
            )

            payload = result["payload"]

            source = (
                payload.get("source")
                or payload.get("Source PDF")
                or payload.get("file")
            )

            if source and source not in sources:
                sources.append(source)

        context = "\n\n".join(
            context_parts
        )[:4000]

        prompt = PROMPT.format(
            context=context,
            question=question
        )

        response = self.llm.invoke(
            prompt
        )

        return {
            "status": "success",
            "answer": response.content,
            "sources": sources
        }

    def close(self):

        self.retriever.close()