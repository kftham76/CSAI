import re

import pandas as pd

from csai_langchain.repositories.company_repository import (
    CompanyRepository,
)


class EntityExtractor:

    GENERIC_COMPANY_WORDS = {
        "SDN",
        "BHD",
        "BERHAD",
        "PRIVATE",
        "LIMITED",
        "LTD",
        "COMPANY",
        "CO",
        "MALAYSIA",
        "M",
    }

    def __init__(self):

        self.repo = CompanyRepository()

        companies = self.repo.get_all_companies()

        company_map = {}
        self.people = set()

        for row in companies:

            ####################################################
            # Company lookup
            ####################################################

            company = row.get(
                "Company Name",
                ""
            )

            if (
                company
                and not pd.isna(company)
            ):

                company = str(
                    company
                ).strip()

                normalized = self.normalize(
                    company
                )

                if normalized:

                    company_map[
                        normalized
                    ] = company

            ####################################################
            # Director lookup
            ####################################################

            for index in range(
                1,
                50
            ):

                key = (
                    f"Director{index} Name"
                )

                if key not in row:
                    break

                name = row.get(
                    key
                )

                if (
                    name is None
                    or pd.isna(name)
                ):
                    continue

                name = self.normalize(
                    str(name)
                )

                if name:

                    self.people.add(
                        name
                    )

        ####################################################
        # Store unique company records
        ####################################################

        self.company_lookup = []

        for normalized, company in company_map.items():

            significant_tokens = (
                self.get_significant_company_tokens(
                    normalized
                )
            )

            self.company_lookup.append({
                "normalized": normalized,
                "company": company,
                "tokens": significant_tokens,
            })

        # Longer, more specific companies should be checked first.
        self.company_lookup.sort(
            key=lambda item: (
                len(item["tokens"]),
                len(item["normalized"]),
            ),
            reverse=True
        )

    ####################################################
    # Normalize
    ####################################################

    @staticmethod
    def normalize(text):

        if (
            text is None
            or pd.isna(text)
        ):
            return ""

        text = str(
            text
        ).upper()

        text = text.replace(
            "&",
            " AND "
        )

        text = re.sub(
            r"[^A-Z0-9\s]",
            " ",
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text.strip()

    ####################################################
    # Significant company tokens
    ####################################################

    def get_significant_company_tokens(
        self,
        normalized_company
    ):

        return tuple(
            token

            for token
            in normalized_company.split()

            if (
                token
                not in self.GENERIC_COMPANY_WORDS
                and len(token) >= 2
            )
        )

    ####################################################
    # Company Extraction
    ####################################################

    def extract_company(
        self,
        question
    ):

        normalized_question = (
            self.normalize(
                question
            )
        )

        if not normalized_question:
            return ""

        question_tokens = set(
            normalized_question.split()
        )

        ####################################################
        # Exact full company-name match
        ####################################################

        padded_question = (
            f" {normalized_question} "
        )

        exact_matches = []

        for item in self.company_lookup:

            normalized_company = item[
                "normalized"
            ]

            if (
                f" {normalized_company} "
                in padded_question
            ):

                exact_matches.append(
                    item
                )

        if exact_matches:

            exact_matches.sort(
                key=lambda item: len(
                    item["normalized"]
                ),
                reverse=True
            )

            return exact_matches[
                0
            ]["company"]

        ####################################################
        # Significant-token match
        ####################################################

        candidates = []

        for item in self.company_lookup:

            company_tokens = item[
                "tokens"
            ]

            if not company_tokens:
                continue

            token_set = set(
                company_tokens
            )

            ################################################
            # Multi-word company
            ################################################

            if len(token_set) >= 2:

                if token_set.issubset(
                    question_tokens
                ):

                    candidates.append(
                        item
                    )

            ################################################
            # Single meaningful company word
            ################################################

            elif len(token_set) == 1:

                token = next(
                    iter(token_set)
                )

                if (
                    len(token) >= 5
                    and token
                    in question_tokens
                ):

                    candidates.append(
                        item
                    )

        if not candidates:
            return ""

        ####################################################
        # Choose most specific candidate
        ####################################################

        candidates.sort(
            key=lambda item: (
                len(item["tokens"]),
                len(item["normalized"]),
            ),
            reverse=True
        )

        best = candidates[0]

        best_score = (
            len(best["tokens"]),
            len(best["normalized"]),
        )

        tied_companies = {
            item["company"]

            for item in candidates

            if (
                len(item["tokens"]),
                len(item["normalized"]),
            ) == best_score
        }

        # Never select randomly when matching is ambiguous.
        if len(tied_companies) != 1:
            return ""

        return best["company"]

    ####################################################
    # Person Extraction
    ####################################################

    def extract_person(
        self,
        question
    ):

        normalized_question = (
            self.normalize(
                question
            )
        )

        if not normalized_question:
            return ""

        question_tokens = set(
            normalized_question.split()
        )

        candidates = []

        for person in self.people:

            person_tokens = tuple(
                person.split()
            )

            if not person_tokens:
                continue

            if set(
                person_tokens
            ).issubset(
                question_tokens
            ):

                candidates.append(
                    person
                )

        if not candidates:
            return ""

        candidates.sort(
            key=lambda person: (
                len(person.split()),
                len(person),
            ),
            reverse=True
        )

        best_person = candidates[
            0
        ]

        best_score = (
            len(best_person.split()),
            len(best_person),
        )

        tied_people = {
            person

            for person in candidates

            if (
                len(person.split()),
                len(person),
            ) == best_score
        }

        if len(tied_people) != 1:
            return ""

        return best_person