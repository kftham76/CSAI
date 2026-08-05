import json
import re

import pandas as pd

from csai_langchain.config.settings import (
    COMPANY_ALIASES_FILE,
)
from csai_langchain.repositories.company_repository import (
    CompanyRepository,
)
from csai_langchain.repositories.auditor_repository import (
    AuditorRepository,
)
from csai_langchain.repositories.ebos_repository import (
    EBOSRepository,
)
from csai_langchain.repositories.constitution_repository import (
    ConstitutionRepository,
)
from csai_langchain.repositories.financial_statement_repository import (
    FinancialStatementRepository,
)


class EntityExtractor:

    COMPANY_FIELD_ALIASES = {
        "COMPANY NUMBER": "Reg No",
        "REGISTRATION NUMBER": "Reg No",
        "REGISTRATION NO": "Reg No",
        "REG NO": "Reg No",
        "ANNUAL RETURN DATE": "Annual Return Date",
        "ANNUAL RETRUN DATE": "Annual Return Date",
        "ANUAL RETURN DATE": "Annual Return Date",
        "ANUAL RETRUN DATE": "Annual Return Date",
        "ANNUAL RETURN LODGEMENT DATE": (
            "Date of Lodgement (AR)"
        ),
        "AR LODGEMENT DATE": "Date of Lodgement (AR)",
        "DATE OF LODGEMENT AR": "Date of Lodgement (AR)",
        "SECTION 51 DATE": "Section 51 Date",
        "SEC 51 DATE": "Section 51 Date",
        "S51 DATE": "Section 51 Date",
        "SECTION 58 DATE": "Section 58 Date",
        "SEC 58 DATE": "Section 58 Date",
        "S58 DATE": "Section 58 Date",
        "SECTION 78 DATE": "Section 78 Date",
        "SEC 78 DATE": "Section 78 Date",
        "S78 DATE": "Section 78 Date",
        "INCORPORATION DATE": "Incorporate Date",
        "INCORPORATE DATE": "Incorporate Date",
        "INCORPORATED DATE": "Incorporate Date",
        "DATE INCORPORATED": "Incorporate Date",
        "INCOPERATION DATE": "Incorporate Date",
        "INCOPORATION DATE": "Incorporate Date",
        "INCORPORATION": "Incorporate Date",
        "TOTAL ISSUED SHARES": "Total Issued Shares",
        "ISSUED SHARES": "Total Issued Shares",
        "BUSINESS ADDRESS": "Business Address",
        "FINANCIAL RECORD ADDRESS": (
            "Financial Record Address"
        ),
        "ACCOUNTING RECORD ADDRESS": (
            "Financial Record Address"
        ),
        "LAST UPDATED": "UpdatedAt",
        "UPDATED AT": "UpdatedAt",
    }

    MONTH_ALIASES = {
        "JAN": "JANUARY",
        "JANUARY": "JANUARY",
        "FEB": "FEBRUARY",
        "FEBRUARY": "FEBRUARY",
        "MAR": "MARCH",
        "MARCH": "MARCH",
        "APR": "APRIL",
        "APRIL": "APRIL",
        "MAY": "MAY",
        "JUN": "JUNE",
        "JUNE": "JUNE",
        "JUL": "JULY",
        "JULY": "JULY",
        "AUG": "AUGUST",
        "AUGUST": "AUGUST",
        "SEP": "SEPTEMBER",
        "SEPT": "SEPTEMBER",
        "SEPTEMBER": "SEPTEMBER",
        "OCT": "OCTOBER",
        "OCTOBER": "OCTOBER",
        "NOV": "NOVEMBER",
        "NOVEMBER": "NOVEMBER",
        "DEC": "DECEMBER",
        "DECEMBER": "DECEMBER",
    }

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
        self.auditor_repo = AuditorRepository()
        self.ebos_repo = EBOSRepository()
        self.constitution_repo = ConstitutionRepository()
        self.financial_statement_repo = FinancialStatementRepository()

        companies = self.repo.get_all_companies()
        auditor_companies = (
            self.auditor_repo.get_all_records()
        )
        ebos_companies = (
            self.ebos_repo.get_all_company_names()
        )
        constitution_companies = (
            self.constitution_repo.get_all_company_names()
        )
        financial_statement_companies = (
            self.financial_statement_repo.get_all_company_names()
        )

        company_map = {}
        self.people = set()
        self.company_columns = tuple(
            companies[0].keys()
            if companies
            else ()
        )

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
            # Shareholder/member lookup
            ####################################################

            for index in range(
                1,
                50
            ):

                key = (
                    f"Member{index} Name"
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
        # Auxiliary database company lookup
        ####################################################

        for records in (
            auditor_companies,
            ebos_companies,
            constitution_companies,
            financial_statement_companies,
        ):

            for row in records:

                company = row.get(
                    "Company Name",
                    ""
                )

                if (
                    company is None
                    or pd.isna(company)
                ):
                    continue

                company = str(company).strip()
                normalized = self.normalize(company)

                if normalized:
                    # Client_Master was loaded first, so
                    # preserve its canonical spelling.
                    company_map.setdefault(
                        normalized,
                        company,
                    )

        ####################################################
        # Beneficial-owner lookup
        ####################################################

        for name in (
            self.ebos_repo
            .get_all_person_names()
        ):

            normalized_name = self.normalize(
                name
            )

            if normalized_name:

                self.people.add(
                    normalized_name
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
        # Load company aliases
        ####################################################

        self.company_alias_lookup = (
            self._load_company_aliases()
        )

        # Longer aliases should be checked first.
        self.company_alias_items = sorted(
            self.company_alias_lookup.items(),
            key=lambda item: (
                len(item[0].split()),
                len(item[0]),
            ),
            reverse=True
        )

        ####################################################
        # Auditor company and firm lookups
        ####################################################

        self.auditor_company_lookup = (
            self._build_company_lookup(
                auditor_companies
            )
        )

        self.auditor_alias_lookup = (
            self._build_auditor_alias_lookup(
                companies,
                auditor_companies
            )
        )

        self.auditor_alias_items = sorted(
            self.auditor_alias_lookup.items(),
            key=lambda item: (
                len(item[0].split()),
                len(item[0]),
            ),
            reverse=True
        )

        self.auditor_lookup = []

        for row in (
            self.auditor_repo
            .get_distinct_auditors()
        ):

            auditor = (
                row.get(
                    "Auditor Name",
                    ""
                )
                or ""
            ).strip()

            normalized = (
                self.auditor_repo
                .normalize_auditor(
                    auditor
                )
            )

            if not normalized:
                continue

            tokens = tuple(
                token

                for token in normalized.split()

                if token not in {
                    "AND",
                    "ASSOCIATES",
                    "CO",
                    "FIRM",
                    "MALAYSIA",
                    "PARTNERS",
                    "PLT",
                }
            )

            self.auditor_lookup.append({
                "normalized": normalized,
                "auditor": auditor,
                "tokens": tokens,
            })

        self.auditor_lookup.sort(
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

    def extract_company_fields(self, question):

        normalized_question = self.normalize(
            question
        )

        if not normalized_question:
            return ()

        padded_question = (
            f" {normalized_question} "
        )

        matches = []

        aliases = sorted(
            self.COMPANY_FIELD_ALIASES.items(),
            key=lambda item: len(item[0]),
            reverse=True
        )

        for alias, column in aliases:

            if f" {alias} " not in padded_question:
                continue

            if column not in matches:
                matches.append(column)

        normalized_columns = sorted(
            (
                (
                    self.normalize(column),
                    column,
                )
                for column in self.company_columns
            ),
            key=lambda item: len(item[0]),
            reverse=True
        )

        for normalized_column, column in normalized_columns:

            if (
                not normalized_column
                or f" {normalized_column} "
                not in padded_question
            ):
                continue

            if column not in matches:
                matches.append(column)

        return tuple(matches)

    ####################################################
    # Financial year end extraction
    ####################################################

    @classmethod
    def extract_financial_year_end(
        cls,
        question
    ):

        normalized = cls.normalize(
            question
        )

        if not normalized:
            return ""

        month_pattern = "|".join(
            sorted(
                cls.MONTH_ALIASES,
                key=len,
                reverse=True
            )
        )

        day_first = re.search(
            (
                r"\b(\d{1,2})"
                r"(?:ST|ND|RD|TH)?\s+"
                rf"({month_pattern})\b"
            ),
            normalized
        )

        if day_first:

            day = int(
                day_first.group(1)
            )

            if 1 <= day <= 31:
                return (
                    f"{day} "
                    f"{cls.MONTH_ALIASES[day_first.group(2)]}"
                )

        month_first = re.search(
            (
                rf"\b({month_pattern})\s+"
                r"(\d{1,2})"
                r"(?:ST|ND|RD|TH)?\b"
            ),
            normalized
        )

        if month_first:

            day = int(
                month_first.group(2)
            )

            if 1 <= day <= 31:
                return (
                    f"{day} "
                    f"{cls.MONTH_ALIASES[month_first.group(1)]}"
                )

        fye_term = (
            r"(?:FINANCIAL\s+YEAR\s+END|FYE)"
        )

        after_term = re.search(
            (
                fye_term
                + r"(?:\s+(?:IN|OF|ON|IS|AT))?\s+"
                + rf"({month_pattern})\b"
            ),
            normalized
        )

        if after_term:
            return cls.MONTH_ALIASES[
                after_term.group(1)
            ]

        before_term = re.search(
            (
                rf"\b({month_pattern})"
                r"(?:\s+(?:A|THE))?\s+"
                + fye_term
                + r"\b"
            ),
            normalized
        )

        if before_term:
            return cls.MONTH_ALIASES[
                before_term.group(1)
            ]

        all_companies = re.search(
            (
                r"\b(?:ALL|EVERY|EACH)\s+"
                r"(?:THE\s+)?"
                r"COMPAN(?:Y|IES)\b"
            ),
            normalized
        )

        if all_companies:
            return "ALL"

        return ""

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
    # Build company lookup
    ####################################################

    def _build_company_lookup(
        self,
        rows
    ):

        company_map = {}

        for row in rows:

            company = row.get(
                "Company Name",
                ""
            )

            if (
                not company
                or pd.isna(company)
            ):
                continue

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

        lookup = []

        for normalized, company in company_map.items():

            lookup.append({
                "normalized": normalized,
                "company": company,
                "tokens":
                    self.get_significant_company_tokens(
                        normalized
                    ),
            })

        lookup.sort(
            key=lambda item: (
                len(item["tokens"]),
                len(item["normalized"]),
            ),
            reverse=True
        )

        return lookup

    ####################################################
    # Remap aliases to auditor company names
    ####################################################

    def _build_auditor_alias_lookup(
        self,
        client_rows,
        auditor_rows
    ):

        client_registration = {}

        for row in client_rows:

            company = self.normalize(
                row.get(
                    "Company Name",
                    ""
                )
            )

            registration = str(
                row.get(
                    "Reg No",
                    ""
                )
                or ""
            ).strip()

            if company:

                client_registration[
                    company
                ] = registration

        auditor_by_registration = {}
        auditor_by_name = {}

        for row in auditor_rows:

            company = (
                row.get(
                    "Company Name",
                    ""
                )
                or ""
            )

            if not company:
                continue

            company = str(
                company
            ).strip()

            normalized = self.normalize(
                company
            )

            registration = str(
                row.get(
                    "Reg No",
                    ""
                )
                or ""
            ).strip()

            if normalized:

                auditor_by_name[
                    normalized
                ] = company

            if registration:

                auditor_by_registration[
                    registration
                ] = company

        alias_lookup = {}

        for alias, client_company in (
            self.company_alias_lookup.items()
        ):

            normalized_client = self.normalize(
                client_company
            )

            registration = (
                client_registration.get(
                    normalized_client,
                    ""
                )
            )

            auditor_company = (
                auditor_by_registration.get(
                    registration
                )
                if registration
                else ""
            )

            if not auditor_company:

                auditor_company = (
                    auditor_by_name.get(
                        normalized_client,
                        ""
                    )
                )

            if auditor_company:

                alias_lookup[
                    alias
                ] = auditor_company

        return alias_lookup

    ####################################################
    # Load company aliases
    ####################################################

    def _load_company_aliases(
        self
    ):

        if not COMPANY_ALIASES_FILE.exists():
            return {}

        with COMPANY_ALIASES_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            alias_data = json.load(
                file
            )

        if not isinstance(
            alias_data,
            dict
        ):
            raise ValueError(
                "company_aliases.json must contain "
                "a JSON object."
            )

        registered_companies = {
            item["normalized"]: item["company"]
            for item in self.company_lookup
        }

        alias_lookup = {}

        for registered_name, aliases in alias_data.items():

            normalized_registered_name = (
                self.normalize(
                    registered_name
                )
            )

            canonical_company = (
                registered_companies.get(
                    normalized_registered_name
                )
            )

            if not canonical_company:
                raise ValueError(
                    "Company in company_aliases.json "
                    "was not found in Client_Master: "
                    f"{registered_name}"
                )

            if isinstance(
                aliases,
                str
            ):
                aliases = [
                    aliases
                ]

            if not isinstance(
                aliases,
                list
            ):
                raise ValueError(
                    "Aliases for "
                    f"{registered_name} "
                    "must be a string or list."
                )

            for alias in aliases:

                normalized_alias = (
                    self.normalize(
                        alias
                    )
                )

                if not normalized_alias:
                    continue

                existing_company = (
                    alias_lookup.get(
                        normalized_alias
                    )
                )

                if (
                    existing_company
                    and existing_company
                    != canonical_company
                ):
                    raise ValueError(
                        "Duplicate company alias "
                        "detected: "
                        f"{alias} maps to both "
                        f"{existing_company} and "
                        f"{canonical_company}."
                    )

                alias_lookup[
                    normalized_alias
                ] = canonical_company

        return alias_lookup

    ####################################################
    # Company Extraction
    ####################################################

    def extract_company(
        self,
        question
    ):

        return self._extract_company(
            question,
            self.company_lookup,
            self.company_alias_items
        )

    def extract_auditor_company(
        self,
        question
    ):

        return self._extract_company(
            question,
            self.auditor_company_lookup,
            self.auditor_alias_items
        )

    def _extract_company(
        self,
        question,
        company_lookup,
        alias_items
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

        for item in company_lookup:

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
        # Company alias match
        ####################################################

        alias_matches = []

        for alias, company in (
            alias_items
        ):

            if (
                f" {alias} "
                in padded_question
            ):

                alias_matches.append({
                    "alias": alias,
                    "company": company,
                })

        if alias_matches:

            best_alias_score = (
                len(
                    alias_matches[0]["alias"].split()
                ),
                len(
                    alias_matches[0]["alias"]
                ),
            )

            best_companies = {
                item["company"]

                for item in alias_matches

                if (
                    len(
                        item["alias"].split()
                    ),
                    len(
                        item["alias"]
                    ),
                ) == best_alias_score
            }

            # Never select randomly when matching is ambiguous.
            if len(best_companies) == 1:
                return next(
                    iter(
                        best_companies
                    )
                )

            return ""

        ####################################################
        # Significant-token match
        ####################################################

        candidates = []

        for item in company_lookup:

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
    # Auditor Extraction
    ####################################################

    def extract_auditor(
        self,
        question
    ):

        normalized_question = (
            self.auditor_repo
            .normalize_auditor(
                question
            )
        )

        if not normalized_question:
            return ""

        question_tokens = set(
            normalized_question.split()
        )

        padded_question = (
            f" {normalized_question} "
        )

        exact_matches = [
            item

            for item in self.auditor_lookup

            if (
                f" {item['normalized']} "
                in padded_question
            )
        ]

        if exact_matches:

            exact_matches.sort(
                key=lambda item: len(
                    item["normalized"]
                ),
                reverse=True
            )

            return exact_matches[
                0
            ]["auditor"]

        candidates = []

        for item in self.auditor_lookup:

            tokens = set(
                item["tokens"]
            )

            if (
                tokens
                and tokens.issubset(
                    question_tokens
                )
            ):

                candidates.append(
                    item
                )

        if not candidates:
            return ""

        candidates.sort(
            key=lambda item: (
                len(item["tokens"]),
                len(item["normalized"]),
            ),
            reverse=True
        )

        best_token_count = len(
            candidates[0]["tokens"]
        )

        tied_auditors = {
            item["auditor"]

            for item in candidates

            if len(
                item["tokens"]
            ) == best_token_count
        }

        if len(tied_auditors) != 1:
            return ""

        return next(
            iter(
                tied_auditors
            )
        )

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
