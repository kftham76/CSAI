import sys
sys.path.insert(0, r"C:\CSAI_OS")


from csai_langchain.Retrieval.router import route_query

print(
    route_query(
        "Who are the shareholders of Action Multiple Sdn Bhd?"
    )
)