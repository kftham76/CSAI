import importlib
import pkgutil
import sys
import traceback

import csai_langchain


SKIP_MODULES = {
    "csai_langchain.test",
    "csai_langchain.test_imports",
    "csai_langchain.test_qdrant_sources",
    "csai_langchain.test_rag_retrieval",
}


def main():

    imported_count = 0
    failures = []

    print("=" * 80)
    print("CSAI IMPORT TEST")
    print("=" * 80)

    for module_info in pkgutil.walk_packages(
        csai_langchain.__path__,
        prefix="csai_langchain."
    ):

        module_name = module_info.name

        if module_name in SKIP_MODULES:
            continue

        print(
            "Importing:",
            module_name
        )

        try:

            importlib.import_module(
                module_name
            )

            imported_count += 1

        except Exception as error:

            failures.append({
                "module": module_name,
                "error": str(error),
                "traceback": traceback.format_exc(),
            })

    print()
    print("=" * 80)
    print("IMPORT SUMMARY")
    print("=" * 80)

    print(
        "Successfully imported:",
        imported_count
    )

    print(
        "Failed imports:",
        len(failures)
    )

    for failure in failures:

        print()
        print("-" * 80)

        print(
            "MODULE:",
            failure["module"]
        )

        print(
            "ERROR:",
            failure["error"]
        )

        print(
            failure["traceback"]
        )

    if failures:

        return 1

    print()
    print(
        "All CSAI modules imported successfully."
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )