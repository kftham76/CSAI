import time
import atexit

from langchain_ollama import ChatOllama
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from csai_langchain.Retrieval.router import route

from csai_langchain.Retrieval.metadata_search import (
    init,
    search_company,
    search_person_role,
    search_person,
    search_by_auditor
)

from csai_langchain.service.response_formatter import (
    build_response
)

from csai_langchain.tools.director_tools import (
    get_directors,
    get_person_directorship
)

from csai_langchain.tools.shareholder_tools import (
    get_shareholders
)

#########################################################
# CONFIG
#########################################################

QDRANT_PATH = r"C:\CSAI_OS\07 Qdrant\storage"

QDRANT_COLLECTION = "csai_master"

SIMILARITY_THRESHOLD = 0.70
MAX_CONTEXT = 4000

#########################################################
# LOAD MODELS
#########################################################

print("Loading Embedding Model...")

embedding_model = SentenceTransformer(
    "BAAI/bge-small-en-v1.5"
)

print("Loading GPT-OSS...")

llm = ChatOllama(
    model="gpt-oss:20b",
    temperature=0,
    base_url="http://127.0.0.1:11434"
)

client = QdrantClient(
    path=QDRANT_PATH
)

init(client)

print("CSAI Ready")

atexit.register(
    lambda: client.close()
)

#########################################################
# MAIN
#########################################################


def ask_csai(question):

    start = time.time()

    #####################################################
    # ROUTER
    #####################################################

    route_result = route(question)

    intent = route_result.get(
        "intent",
        "knowledge"
    )

    company = route_result.get(
        "company",
        ""
    )

    person = route_result.get(
        "person",
        ""
    )
    #####################################################
# ROUTER FIX
#####################################################

    if intent == "person_directorship":

        company = ""

        if not person:

            import re

            patterns = [

                r'which companies is (.*?) appointed',

                r'companies (?:is|are)? (.*?) appointed',

                r'companies associated with (.*)',

                r'directorship of (.*)',

                r'(.*?) appointed as director'
            ]

            for p in patterns:

                m = re.search(
                    p,
                    question,
                    re.I
                )

                if m:

                    person = (
                        m.group(1)
                        .strip()
                        .upper()
                    )

                    break
    print(
    f"\nIntent={intent}"
    f" Company={company}"
    f" Person={person}"
)

    #####################################################
    # GENERAL CHAT
    #####################################################

    if intent in [
        "knowledge",
        "greeting"
    ]:

        response = llm.invoke(
            question
        )

        return {
            "status": "success",
            "intent": intent,
            "answer": response.content
        }

    #####################################################
    # DIRECTOR
    #####################################################

    if intent == "director":

        data = get_directors(company)

        print("\nDIRECTOR RESULT:")
        print(data)
        print("COUNT:", len(data))

        return build_response(
            intent=intent,
            company=company,
            results=data
    )

    #####################################################
    # SHAREHOLDER / BO
    #####################################################

    if intent in [
        "shareholder",
        "beneficial_owner"
    ]:

        data = get_shareholders(
            company
        )

        return build_response(
            intent=intent,
            company=company,
            results=data
        )

    #####################################################
    # PERSON DIRECTORSHIP
    #####################################################

    if intent == "person_directorship":

        data = get_person_directorship(
            person
        )

        answer = ""

        if data:

            answer = (
                f"{person} is appointed "
                f"as director in "
                f"{len(data)} companies."
            )

        print(
            f"\nTime : "
            f"{time.time()-start:.2f}s"
        )

        return {
            "status": "success",
            "intent": intent,
            "person": person,
            "answer": answer,
            "count": len(data),
            "results": data,
            "sources": [
                "Client_Master"
            ]
        }

    #####################################################
    # METADATA SEARCH
    #####################################################

    metadata_results = []

    try:

        if intent == "company":

            metadata_results = (
                search_company(
                    company
                )
            )

        elif intent == "auditor":

            metadata_results = (
                search_by_auditor(
                    company
                )
            )

        elif intent == "person_shareholding":

            metadata_results = (
                search_person_role(
                    person,
                    "SHAREHOLDER"
                )
            )

        elif person:

            metadata_results = (
                search_person(
                    person
                )
            )

    except Exception as e:

        print(
            "Metadata Error:",
            str(e)
        )

    #####################################################
    # DIRECT RETURN
    #####################################################

    if metadata_results:

        structured = []

        for r in metadata_results:

            try:
                structured.append(
                    r.payload
                )
            except:
                structured.append(
                    r
                )

        print(
            f"\nTime : "
            f"{time.time()-start:.2f}s"
        )

        return build_response(
            intent=intent,
            company=company,
            person=person,
            results=structured
        )

    #####################################################
    # VECTOR FALLBACK
    #####################################################

    context = ""

    vector = (
        embedding_model.encode(
            question,
            normalize_embeddings=True
        ).tolist()
    )

    results = (
        client.query_points(
            collection_name=
                QDRANT_COLLECTION,
            query=vector,
            limit=3
        ).points
    )

    if results:

        best_score = (
            results[0].score
        )

        print(
            "Top Score:",
            round(
                best_score,
                4
            )
        )

        if (
            best_score >=
            SIMILARITY_THRESHOLD
        ):

            for r in results:

                text = (
                    r.payload.get(
                        "text",
                        ""
                    )
                )

                if not text:
                    continue

                context += (
                    text[:1000]
                    + "\n\n"
                )

    context = context[
        :MAX_CONTEXT
    ]

    #####################################################
    # NO RESULT
    #####################################################

    if not context.strip():

        return {
            "status":
                "not_found",

            "intent":
                intent,

            "answer":
                "Information not found in database."
        }

    #####################################################
    # FINAL RAG
    #####################################################

    prompt = f"""
Use ONLY the context.

Context:

{context}

Question:

{question}

Answer:
"""

    response = llm.invoke(
        prompt
    )

    print(
        f"\nTime : "
        f"{time.time()-start:.2f}s"
    )

    return {
        "status":
            "success",

        "intent":
            intent,

        "answer":
            response.content
    }


#########################################################
# TEST
#########################################################

if __name__ == "__main__":

    while True:

        q = input(
            "\nCSAI > "
        )

        if q.lower() in [
            "exit",
            "quit"
        ]:
            break

        print(
            ask_csai(q)
        )