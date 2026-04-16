"""Fix all workspace mismatches in the production DB."""
import os, sys, uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load the backend .env
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from pymongo import MongoClient
client = MongoClient(os.getenv("MONGO_URI"))
db = client["nexus_db"]

CORRECT_WS = "Mohit's Workspace"

# 1. Delete the duplicate bad projects (mohit-s-workspace ones)
result = db.projects.delete_many({"workspace": "mohit-s-workspace"})
print(f"[1] Deleted {result.deleted_count} bad 'mohit-s-workspace' duplicate projects")

# 2. Also delete legacy slug-based projects (workspace_slug: "mohit")
result2 = db.projects.delete_many({"workspace_slug": {"$exists": True}})
print(f"[2] Deleted {result2.deleted_count} legacy 'workspace_slug' projects")

# 3. Ensure TESTK exists with correct workspace
testk = db.projects.find_one({"name": "TESTK", "workspace": CORRECT_WS})
if not testk:
    db.projects.insert_one({
        "id": str(uuid.uuid4())[:8],
        "workspace": CORRECT_WS,
        "name": "TESTK",
        "cloneCode": f"{CORRECT_WS}/TESTK",
        "members": [],
        "created_at": datetime.utcnow()
    })
    print("[3] Created TESTK project with correct workspace")
else:
    print("[3] TESTK already exists with correct workspace")

# 4. Fix any project missing workspace field
db.projects.update_many(
    {"workspace": {"$exists": False}},
    {"$set": {"workspace": CORRECT_WS}}
)
print("[4] Fixed any projects missing 'workspace' field")

# 5. Ensure all cloneCodes are in the correct format
for p in db.projects.find():
    expected_cc = f"{CORRECT_WS}/{p['name']}"
    if p.get("cloneCode") != expected_cc:
        db.projects.update_one({"_id": p["_id"]}, {"$set": {"cloneCode": expected_cc}})
        print(f"    Fixed cloneCode: {p.get('cloneCode')} -> {expected_cc}")

# 6. Verify final state
print("\n--- FINAL PROJECT STATE ---")
for p in db.projects.find({}, {"_id": 0, "description": 0, "members": 0}):
    print(f"  workspace={p.get('workspace')} | name={p['name']} | cloneCode={p.get('cloneCode')}")

print("\n--- INCIDENT REPORTS ---")
for r in db.incident_reports.find({}, {"_id": 0, "report_markdown": 0, "hypotheses": 0, "code_locations": 0, "summary": 0}):
    print(f"  workspace={r.get('workspace')} | project={r.get('project')} | id={r.get('incident_id')}")

print("\nDone!")
