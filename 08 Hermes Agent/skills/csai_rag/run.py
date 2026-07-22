import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT))

from csai_langchain.service.csai_service import query


def execute(question):

    return query(question)


if __name__ == "__main__":

    while True:

        q = input("> ")

        print(
            execute(q)
        )