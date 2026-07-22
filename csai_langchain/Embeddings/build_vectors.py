import json
import uuid
import pandas as pd

from pathlib import Path
from sentence_transformers import SentenceTransformer

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct
)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Retrieval"))
from normalizer import normalize_name

JSON_ROOT = Path(r"C:\CSAI_OS\06_LangChain\data_json")
QDRANT_PATH = r"C:\CSAI_OS\07 Qdrant\storage"
COLLECTION_NAME = "csai_master"

print("Loading Embedding Model...")
model = SentenceTransformer("BAAI/bge-small-en-v1.5")
print("Embedding Model Loaded")

client = QdrantClient(path=QDRANT_PATH)

collections = [c.name for c in client.get_collections().collections]

if COLLECTION_NAME in collections:
    client.delete_collection(COLLECTION_NAME)
    print("Deleted existing collection")

client.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
)
print("Collection Created")

points = []
json_files = list(JSON_ROOT.rglob("*.json"))
print("JSON Files Found:", len(json_files))


def add_point(text, payload):
    vector = model.encode(text, normalize_embeddings=True).tolist()
    points.append(PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload))


for file in json_files:
    print("Reading:", file)
    with open(file, "r", encoding="utf-8") as f:
        rows = json.load(f)

    for row in rows:
        company = str(row.get("Company Name", "") or "")
        source = file.stem

        if source == "Client_Master":
            # Company profile point
            company_fields = ["Folder", "Company Name", "Reg No", "Annual Return Date",
                              "Total Issued Shares", "Date of Lodgement section 68",
                              "Business Address", "Financial Record Address",
                              "Auditor Firm No", "Auditor Name", "Auditor Address"]
            comp_text = ""
            for k in company_fields:
                v = row.get(k)
                if pd.notna(v) and v:
                    comp_text += f"{k}: {v}\n"
            if comp_text.strip():
                auditor_name = str(row.get("Auditor Name", "") or "")
                add_point(comp_text, {
                    "text": comp_text,
                    "company": company,
                    "company_std": normalize_name(company),
                    "name": "",
                    "role": "company",
                    "ic": "",
                    "auditor": auditor_name,
                    "auditor_std": normalize_name(auditor_name),
                    "source": source
                })

            # Director records (Director1..Director5)
            for i in range(1, 6):
                name_key = f"Director{i} Name"
                ic_key = f"Director{i} IC"
                dir_name = str(row.get(name_key, "") or "")
                if not dir_name.strip():
                    continue
                dir_ic = str(row.get(ic_key, "") or "")
                dir_fields = [k for k in row if k.startswith(f"Director{i}") and row.get(k)]
                dir_text = f"Company: {company}\n"
                for k in dir_fields:
                    v = row.get(k)
                    if pd.notna(v) and v:
                        dir_text += f"{k}: {v}\n"
                if not dir_text.strip():
                    dir_text = f"Name: {dir_name}\nCompany: {company}\nRole: Director"
                add_point(dir_text, {
                    "text": dir_text,
                    "company": company,
                    "company_std": normalize_name(company),
                    "name": dir_name,
                    "name_std": normalize_name(dir_name),
                    "role": "director",
                    "designation": "DIRECTOR",
                    "ic": dir_ic,
                    "source": source
                })

            # Member records (Member1..Member10)
            for i in range(1, 11):
                name_key = f"Member{i} Name"
                mem_name = str(row.get(name_key, "") or "")
                if not mem_name.strip():
                    continue
                mem_ic = str(row.get(f"Member{i} ID No", "") or "")
                mem_shares = str(row.get(f"Member{i} Shares", "") or "")
                mem_type = str(row.get(f"Member{i} Type", "") or "")
                mem_text = f"Name: {mem_name}\nCompany: {company}\nRole: Member"
                if mem_shares:
                    mem_text += f"\nShares: {mem_shares}"
                if mem_type:
                    mem_text += f"\nType: {mem_type}"
                if mem_ic:
                    mem_text += f"\nIC: {mem_ic}"
                add_point(mem_text, {
                    "text": mem_text,
                    "company": company,
                    "company_std": normalize_name(company),
                    "name": mem_name,
                    "name_std": normalize_name(mem_name),
                    "role": "member",
                    "designation": "SHAREHOLDER",
                    "ic": mem_ic,
                    "source": source
                })

        else:
            # EBOS_Master — keep existing structure, add role
            text = ""
            for k, v in row.items():
                if pd.isna(v):
                    continue
                if v:
                    text += f"{k}: {v}\n"
            if not text.strip():
                continue

            name = str(row.get("Name", "") or "")
            ic = str(row.get("IC", "") or "")
            designation = str(row.get("Designation", "") or "")
            bo_type = str(row.get("Type of BO", "") or "")
            nationality = str(row.get("Nationality", "") or "")
            category = str(row.get("Category", "") or "")
            client_name = str(row.get("Client", "") or "")

            role = "director" if "DIRECTOR" in designation.upper() else "bo"

            add_point(text, {
                "text": text,
                "company": company,
                "company_std": normalize_name(company),
                "name": name,
                "name_std": normalize_name(name),
                "role": role,
                "ic": ic,
                "designation": designation,
                "bo_type": bo_type,
                "nationality": nationality,
                "category": category,
                "client": client_name,
                "source": source
            })

print("Total Points:", len(points))

BATCH = 500
for i in range(0, len(points), BATCH):
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points[i:i+BATCH]
    )
    print(f"Inserted {min(i+BATCH, len(points))}/{len(points)}")

print("VECTOR BUILD DONE")
