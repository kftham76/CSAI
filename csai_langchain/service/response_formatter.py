def build_response(
        intent,
        answer="",
        company="",
        person="",
        results=None,
        status="success",
        sources=None
):

    if results is None:
        results = []

    if sources is None:
        sources = []

    return {

        "status":
            status,

        "intent":
            intent,

        "company":
            company,

        "person":
            person,

        "answer":
            answer,

        "count":
            len(results),

        "results":
            results,

        "sources":
            sources
    }