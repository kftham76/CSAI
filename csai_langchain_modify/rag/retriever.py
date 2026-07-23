from fastembed import TextEmbedding
from qdrant_client import QdrantClient

from csai_langchain_modify.config.settings import (
    EMBEDDING_MODEL,
    QDRANT_PATH,
    MASTER_COLLECTION,
    TOP_K,
)


FASTEMBED_CACHE = r"C:\CSAI_OS\05 Models\fastembed"


class Retriever:

    def __init__(self):

        print("Loading FastEmbed Model...")

        self.embedding_model = TextEmbedding(
            model_name=EMBEDDING_MODEL,
            cache_dir=FASTEMBED_CACHE
        )

        self.client = QdrantClient(
            path=str(QDRANT_PATH)
        )

        print("FastEmbed Ready")

    def search(self, question):

        if not question or not question.strip():
            return []

        vector = list(
            self.embedding_model.query_embed(
                question.strip()
            )
        )[0].tolist()

        response = self.client.query_points(
            collection_name=MASTER_COLLECTION,
            query=vector,
            limit=TOP_K
        )

        results = []

        for point in response.points:

            payload = point.payload or {}

            text = payload.get("text", "")

            if not text:
                continue

            results.append({
                "score": float(point.score),
                "text": text,
                "payload": payload
            })

        return results

    def close(self):

        self.client.close()