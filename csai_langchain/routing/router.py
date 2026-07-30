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

        # distinct auditor list
        for p in AUDITOR_LIST:
            if p.search(q):
                return Intent(
                    intent="auditor_list",
                    question=question
                )

        # recognized auditor firm
        auditor = self.extractor.extract_auditor(
            question
        )

        if auditor:
            return Intent(
                intent="auditor_companies",
                auditor=auditor,
                question=question
            )

        # reverse auditor lookup with an unknown firm
        for p in AUDITOR_COMPANIES:
            if p.search(q):
                return Intent(
                    intent="auditor_companies",
                    auditor="",
                    question=question
                )

        # company auditor lookup
        for p in AUDITOR:
            if p.search(q):
                return Intent(
                    intent="auditor",
                    company=(
                        self.extractor
                        .extract_auditor_company(
                            question
                        )
                    ),
                    question=question
                )

        # client company-name list
        for p in COMPANY_LIST:
            if p.search(q):
                return Intent(
                    intent="company_list",
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
