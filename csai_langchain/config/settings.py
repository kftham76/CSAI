from pathlib import Path

########################################################
# PROJECT ROOT
########################################################

ROOT = Path(__file__).resolve().parents[2]

########################################################
# DATABASES
########################################################

DB_FOLDER = (
    ROOT
    / "06 Data"
    / "databases"
)

CLIENT_DB = DB_FOLDER / "csai_master.db"

EBOS_DB = DB_FOLDER / "ebos_master.db"

AUDITORS_DB = DB_FOLDER / "auditors.db"

CONSTITUTIONS_DB = DB_FOLDER / "constitutions.db"

########################################################
# COMPANY ALIASES
########################################################

COMPANY_ALIASES_FILE = (
    ROOT
    / "csai_langchain"
    / "config"
    / "company_aliases.json"
)

########################################################
# QDRANT
########################################################

QDRANT_PATH = (
    ROOT
    / "07 Qdrant"
    / "storage"
)

MASTER_COLLECTION = "csai_master"


########################################################
# OLLAMA
########################################################

OLLAMA_URL = "http://127.0.0.1:11434"

LLM_MODEL = "gpt-oss:20b"

ROUTER_MODEL = "llama3.2:3b"

########################################################
# EMBEDDING
########################################################

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

########################################################
# RAG
########################################################

SIMILARITY_THRESHOLD = 0.70

TOP_K = 5
