
import sys

sys.path.insert(
    0,
    r"C:\CSAI_OS"
)

from csai_langchain.tools.company_tools import get_company

from csai_langchain.tools.company_tools import get_company

data = get_company(
    "ACTION MULTIPLE SDN BHD"
)

print(len(data))

for r in data:
    print(
        r["Company Name"]
    )