from csai_langchain.repositories.ebos_repository import EBOSRepository


class BeneficialOwnerTool:

    def __init__(self):
        self.repo = EBOSRepository()

    def execute(self, company_name):

        rows = self.repo.get_current_beneficial_owners(
            company_name
        )

        return self._with_friendly_fields(
            rows
        )

    def get_all_current_beneficial_owners(self):

        rows = (
            self.repo
            .get_all_current_beneficial_owners()
        )

        return self._with_friendly_fields(
            rows
        )

    @staticmethod
    def _with_friendly_fields(rows):

        if not rows:
            return []

        results = []

        for row in rows:

            result = dict(
                row
            )

            # Keep the original friendly output keys while
            # also returning the exact EBOS source fields.
            result[
                "Direct Ownership %"
            ] = row.get(
                "Criteria A - Direct Ownership %"
            )
            result[
                "Voting Shares %"
            ] = row.get(
                "Criteria B - Voting Shares %"
            )

            results.append(
                result
            )

        return results
