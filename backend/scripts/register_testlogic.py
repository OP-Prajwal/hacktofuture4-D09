"""Register TESTLOGIC project in the production DB."""
import os, uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from pymongo import MongoClient
client = MongoClient(os.getenv("MONGO_URI"))
db = client["nexus_db"]

WS = "Mohit's Workspace"
NAME = "TESTLOGIC"

existing = db.projects.find_one({"name": NAME, "workspace": WS})
if existing:
    print(f"TESTLOGIC already exists in DB (id={existing['id']})")
else:
    doc = {
        "id": str(uuid.uuid4())[:8],
        "workspace": WS,
        "name": NAME,
        "cloneCode": f"{WS}/{NAME}",
        "members": [],
        "created_at": datetime.utcnow()
    }
    db.projects.insert_one(doc)
    print(f"Created TESTLOGIC project (id={doc['id']})")
