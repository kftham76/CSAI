from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue
)

QDRANT_PATH = r"C:\CSAI_OS\07 Qdrant\storage"

client = QdrantClient(
    path=QDRANT_PATH
)


def search_person(name):

    results = client.scroll(

        collection_name="csai_master",

        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="name",
                    match=MatchValue(
                        value=name.upper()
                    )
                )
            ]
        ),

        limit=100
    )[0]

    return results