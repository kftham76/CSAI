from .patterns import *
from .entity_extractor import EntityExtractor
from csai_langchain.domain.intent import Intent


class Router:

    def __init__(self):
        self.extractor = EntityExtractor()

    def detect(self, question):

        q = question.lower()

        # person directorship
        for p in PERSON_DIRECTORSHIP:
            if p.search(q):
                return Intent(
                    intent="person_directorship",
                    person=self.extractor.extract_person(question),
                    question=question
                )

        # beneficial owner
        for p in BENEFICIAL_OWNER:
            if p.search(q):
                return Intent(
                    intent="beneficial_owner",
                    company=self.extractor.extract_company(question),
                    question=question
                )

        # shareholder
        for p in SHAREHOLDER:
            if p.search(q):
                return Intent(
                    intent="shareholder",
                    company=self.extractor.extract_company(question),
                    question=question
                )

        # director
        for p in DIRECTOR:
            if p.search(q):
                return Intent(
                    intent="director",
                    company=self.extractor.extract_company(question),
                    question=question
                )

        return Intent(
            intent="knowledge",
            question=question
        )