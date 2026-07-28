from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from csai_langchain.config.settings import (
    EMBEDDING_MODEL,
    QDRANT_PATH,
    TOP_K,
)


class Retriever:

    def __init__(
        self,
        collection_name
    ):

        collection_name = (
            collection_name
            or ""
        ).strip()

        if not collection_name:

            raise ValueError(
                "A Qdrant collection name is required."
            )

        self.collection_name = collection_name

        self.embedding_model = SentenceTransformer(
            EMBEDDING_MODEL
        )

        self.client = QdrantClient(
            path=str(QDRANT_PATH)
        )

        self._closed = False

    def search(
        self,
        question
    ):

        if self._closed:

            raise RuntimeError(
                "Retriever has already been closed."
            )

        question = (
            question
            or ""
        ).strip()

        if not question:
            return []

        vector = self.embedding_model.encode(
            question,
            normalize_embeddings=True
        ).tolist()

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=TOP_K
        )

        results = []

        for point in response.points:

            payload = point.payload or {}

            text = (
                payload.get(
                    "text",
                    ""
                )
                or ""
            ).strip()

            if not text:
                continue

            results.append({
                "score": float(point.score),
                "text": text,
                "payload": payload
            })

        return results

    def close(self):

        if self._closed:
            return

        if self.client is not None:

            client = self.client
            self.client = None

            client.close()

        self._closed = True