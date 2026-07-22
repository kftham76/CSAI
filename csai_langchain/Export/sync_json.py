import subprocess
from pathlib import Path

BASE = Path(r"C:\CSAI_OS\06 LangChain")

print("Updating JSON...")

subprocess.run([
    "python",
    str(BASE / "Export" / "sqlite_to_json.py")
])

print("JSON Sync Complete.")