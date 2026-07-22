import re

def extract_company(question):

    pattern = re.search(

        r"of (.+)",

        question,

        re.IGNORECASE
    )

    if pattern:

        return pattern.group(1).strip()

    return None