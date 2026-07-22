from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

QDRANT_PATH = r"C:\CSAI_OS\07 Qdrant\storage"

client = QdrantClient(
    path=QDRANT_PATH
)

model = SentenceTransformer(
    "BAAI/bge-small-en-v1.5"
)


def vector_search(question):

    vector = model.encode(
        question,
        normalize_embeddings=True
    ).tolist()

    results = client.query_points(

        collection_name="csai_master",

        query=vector,

        limit=20

    ).points

    return results