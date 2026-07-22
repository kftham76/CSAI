from sentence_transformers import SentenceTransformer


MODEL_NAME = "BAAI/bge-small-en-v1.5"

embeddings = SentenceTransformer(
    MODEL_NAME
)