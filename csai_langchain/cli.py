import json
import sys
from dataclasses import asdict, is_dataclass

from csai_langchain.routing.router import Router
from csai_langchain.service.csai_service import (
    CSAIService,
)


def serialize_result(result):

    if is_dataclass(result):
        return asdict(result)

    if isinstance(result, dict):
        return result

    return {
        "status": "error",
        "intent": "",
        "answer": "CSAI returned an unsupported response.",
        "company": "",
        "person": "",
        "auditor": "",
        "count": 0,
        "results": [],
        "sources": [],
    }


def error_result(message):

    return {
        "status": "error",
        "intent": "",
        "answer": message,
        "company": "",
        "person": "",
        "auditor": "",
        "count": 0,
        "results": [],
        "sources": [],
    }


def main():

    # Ensure Malaysian names and Unicode characters
    # are printed correctly on Windows.
    try:
        sys.stdout.reconfigure(
            encoding="utf-8"
        )
    except Exception:
        pass

    question = " ".join(
        sys.argv[1:]
    ).strip()

    if not question:

        print(
            json.dumps(
                error_result(
                    "No question was provided."
                ),
                ensure_ascii=False
            )
        )

        return 1

    router = Router()
    service = CSAIService()

    try:

        intent = router.detect(
            question
        )

        result = service.execute(
            intent
        )

        payload = serialize_result(
            result
        )

        print(
            json.dumps(
                payload,
                ensure_ascii=False,
                default=str
            )
        )

        return 0

    except Exception as error:

        print(
            json.dumps(
                error_result(
                    str(error)
                ),
                ensure_ascii=False
            )
        )

        return 1

    finally:

        service.close()


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
