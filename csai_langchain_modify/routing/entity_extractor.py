import re
import pandas as pd

from csai_langchain_modify.repositories.company_repository import CompanyRepository


class EntityExtractor:

    def __init__(self):

        self.repo = CompanyRepository()

        companies = self.repo.get_all_companies()

        self.company_lookup = []

        self.people = set()

        for row in companies:

            ####################################################
            # Company lookup
            ####################################################

            company = row.get("Company Name", "")

            if company:

                self.company_lookup.append(
                    (
                        self.normalize(company),
                        company
                    )
                )

            ####################################################
            # Director lookup
            ####################################################

            for i in range(1, 50):

                key = f"Director{i} Name"

                if key not in row:
                    break

                name = row.get(key)

                if pd.isna(name):
                    continue

                name = str(name).strip().upper()

                if name:
                    self.people.add(name)

    ####################################################
    # Normalize
    ####################################################

    def normalize(self, text):

        if not text:
            return ""

        text = text.upper()

        text = re.sub(
            r"[.,()]",
            "",
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text.strip()

    ####################################################
    # Company Extraction
    ####################################################

    def extract_company(self, question):

        question = self.normalize(question)

        best_company = ""
        best_score = 0

        for normalized, company in self.company_lookup:

            score = 0

            for word in normalized.split():

                if word in question:
                    score += 1

            if score > best_score:

                best_score = score
                best_company = company

        if best_score >= 2:
            return best_company

        return ""

    ####################################################
    # Person Extraction
    ####################################################

    def extract_person(self, question):

        question = question.upper()

        best_person = ""
        best_score = 0

        for person in self.people:

            score = 0

            for word in person.split():

                if word in question:
                    score += 1

            if score > best_score:

                best_score = score
                best_person = person

        if best_score >= 2:
            return best_person

        return ""