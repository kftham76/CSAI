from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

QDRANT_PATH = r"C:\CSAI_OS\07 Qdrant\storage"

model = SentenceTransformer(
    "BAAI/bge-small-en-v1.5"
)

client = QdrantClient(
    path=QDRANT_PATH
)

try:

    while True:

        question = input("\nQuestion : ")

        if question.lower() == "exit":
            break

        vector = model.encode(
            question,
            normalize_embeddings=True
        ).tolist()

        results = client.query_points(
            collection_name="csai_master",
            query=vector,
            limit=5
        ).points

        print("\n========== RESULTS ==========\n")

        for i, r in enumerate(results, start=1):

            print(
                f"Result {i}"
            )

            print(
                f"Score: {r.score:.4f}"
            )

            print(
                r.payload["text"]
            )

            print(
                "-" * 80
            )

finally:

    client.close()