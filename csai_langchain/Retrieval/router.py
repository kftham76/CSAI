import json
import re

from langchain_ollama import ChatOllama

from csai_langchain.Retrieval.normalizer import (
    normalize_match
)

router_llm = ChatOllama(
    model="llama3.2:3b",
    temperature=0,
    num_predict=80,
    format="json",
    base_url="http://127.0.0.1:11434"
)


def route(question):

    q = (
        question
        .lower()
        .replace("?", "")
        .strip()
    )

    #################################################
    # DIRECTOR OF COMPANY
    #################################################

    director_patterns = [

        r"who are the directors of (.+)",
        r"list directors of (.+)",
        r"directors of (.+)"
    ]

    for pattern in director_patterns:

        m = re.search(
            pattern,
            q,
            re.I
        )

        if m:

            company = re.sub(
                r"[?.!,]+$",
                "",
                m.group(1)
            ).strip()

            return {

                "intent":
                    "director",

                "company":
                    normalize_match(
                        company
                    ),

                "person":
                    ""
            }

    #################################################
    # SHAREHOLDER OF COMPANY
    #################################################

    shareholder_patterns = [

        r"who are the shareholders of (.+)",
        r"list shareholders of (.+)",
        r"shareholders of (.+)",
        r"shareholder of (.+)"
    ]

    for pattern in shareholder_patterns:

        m = re.search(
            pattern,
            q,
            re.I
        )

        if m:

            company = re.sub(
                r"[?.!,]+$",
                "",
                m.group(1)
            ).strip()

            return {

                "intent":
                    "shareholder",

                "company":
                    normalize_match(
                        company
                    ),

                "person":
                    ""
            }

    #################################################
    # PERSON DIRECTORSHIP
    #################################################

    if (
        "appointed as director" in q
        or
        "which companies is" in q
        or
        "companies associated with" in q
    ):

        person = q

        person = re.sub(
            r"which companies is",
            "",
            person,
            flags=re.I
        )

        person = re.sub(
            r"appointed as director",
            "",
            person,
            flags=re.I
        )

        person = re.sub(
            r"companies associated with",
            "",
            person,
            flags=re.I
        )

        person = person.strip()

        return {

            "intent":
                "person_directorship",

            "company":
                "",

            "person":
                normalize_match(
                    person
                )
        }

    #################################################
    # PERSON SHAREHOLDING
    #################################################

    if (
        "shareholder of" in q
        and
        "which companies" in q
    ):

        person = q

        person = re.sub(
            r"which companies is",
            "",
            person,
            flags=re.I
        )

        person = re.sub(
            r"shareholder of",
            "",
            person,
            flags=re.I
        )

        person = person.strip()

        return {

            "intent":
                "person_shareholding",

            "company":
                "",

            "person":
                normalize_match(
                    person
                )
        }

    #################################################
    # LLM FALLBACK
    #################################################

    prompt = f"""
Classify the user question.

Possible intents:

director
shareholder
beneficial_owner
company
person_directorship
person_shareholding
auditor
knowledge
greeting

Return ONLY JSON.

Schema:

{{
    "intent":"",
    "company":"",
    "person":""
}}

Examples:

Q:
Who are the shareholders of Action Multiple Sdn Bhd?

A:
{{
    "intent":"shareholder",
    "company":"ACTION MULTIPLE SDN BHD",
    "person":""
}}

Q:
Who are the directors of CTW Global Sdn Bhd?

A:
{{
    "intent":"director",
    "company":"CTW GLOBAL SDN BHD",
    "person":""
}}

Q:
Which companies is KHOR PENG CHAI appointed as director?

A:
{{
    "intent":"person_directorship",
    "company":"",
    "person":"KHOR PENG CHAI"
}}

Question:

{question}
"""

    try:

        response = (
            router_llm.invoke(
                prompt
            ).content
        )

        print(
            "\n========== ROUTER RAW =========="
        )
        print(response)

        response = (
            response
            .replace(
                "```json",
                ""
            )
            .replace(
                "```",
                ""
            )
            .strip()
        )

        match = re.search(
            r"\{.*\}",
            response,
            re.S
        )

        if not match:
            raise Exception(
                "No JSON found"
            )

        data = json.loads(
            match.group()
        )

        result = {

            "intent":
                data.get(
                    "intent",
                    "knowledge"
                ),

            "company":
                normalize_match(
                    data.get(
                        "company",
                        ""
                    )
                ),

            "person":
                normalize_match(
                    data.get(
                        "person",
                        ""
                    )
                )
        }

        print(
            "\nROUTER RESULT:",
            result
        )

        return result

    except Exception as e:

        print(
            "\nRouter Error:",
            str(e)
        )

        return {

            "intent":
                "knowledge",

            "company":
                "",

            "person":
                ""
        }