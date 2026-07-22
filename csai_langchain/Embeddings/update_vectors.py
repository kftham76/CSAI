import subprocess
from pathlib import Path

BASE = Path(r"C:\CSAI_OS\06 LangChain")

print("Rebuilding vectors...")

subprocess.run([
    "python",
    str(BASE / "Embeddings" / "build_vectors.py")
])

print("Vector Update Complete.")