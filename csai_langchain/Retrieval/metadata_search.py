from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue
)
from csai_langchain.Retrieval.normalizer import (
    normalize_match
)

QDRANT_PATH = r"C:\CSAI_OS\07 Qdrant\storage"
COLLECTION = "csai_master"

client = None


def init(qdrant_client):
    global client
    client = qdrant_client

def search_company(company,
                   collection_name=COLLECTION):

    results = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="company_std",
                    match=MatchValue(
                        value=normalize_match(company)
                    )
                )
            ]
        ),
        limit=100
    )

    return results[0]

def search_directors(company,
                     collection_name=COLLECTION):

    results = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[

                FieldCondition(
                    key="company_std",
                    match=MatchValue(
                        value=normalize_match(company)
                    )
                ),

                FieldCondition(
                    key="designation",
                    match=MatchValue(
                        value="DIRECTOR"
                    )
                )

            ]
        ),
        limit=100
    )

    return results[0]

def search_shareholders(company,
                        collection_name=COLLECTION):

    results = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[

                FieldCondition(
                    key="company_std",
                    match=MatchValue(
                        value=normalize_match(company)
                    )
                ),

                FieldCondition(
                    key="designation",
                    match=MatchValue(
                        value="SHAREHOLDER"
                    )
                )

            ]
        ),
        limit=100
    )

    return results[0]

def search_person(person,
                  collection_name=COLLECTION
                  ):

    results = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[

                FieldCondition(
                    key="name_std",
                    match=MatchValue(
                        value=normalize_match(person)
                    )
                )

            ]
        ),
        limit=100
    )

    return results[0]

def search_person_role(
        person,
        role
):

    from qdrant_client.models import (
        Filter as NestedFilter
    )

    results = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[

                FieldCondition(
                    key="name_std",
                    match=MatchValue(
                        value=normalize_match(person)
                    )
                ),

                NestedFilter(
                    should=[

                        FieldCondition(
                            key="designation",
                            match=MatchValue(
                                value=role
                            )
                        ),

                        FieldCondition(
                            key="role",
                            match=MatchValue(
                                value=role.lower()
                            )
                        )

                    ]
                )

            ]
        ),
        limit=100
    )

    return results[0]


def search_by_auditor(auditor_name,
                      collection_name=COLLECTION):

    results = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[

                FieldCondition(
                    key="auditor_std",
                    match=MatchValue(
                        value=normalize_match(auditor_name)
                    )
                )

            ]
        ),
        limit=100
    )

    return results[0]