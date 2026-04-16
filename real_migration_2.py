from backend.db.mongo import mongo
from dotenv import load_dotenv
load_dotenv()

db = mongo.db

# Safely rewrite cloneCodes to use the true literal `workspace` value and the true literal `name` value for every single project
for proj in list(db.projects.find()):
    ws = proj.get("workspace", "Mohit's Workspace")
    name = proj.get("name", "Unknown")
    new_clone_code = f"{ws}/{name}"
    db.projects.update_one({"_id": proj["_id"]}, {"$set": {"cloneCode": new_clone_code}})

db.incident_reports.update_many({'workspace': 'mohit'}, {'$set': {'workspace': 'Mohit\'s Workspace'}})
db.incident_reports.update_many({'workspace': 'mohit-s-workspace'}, {'$set': {'workspace': 'Mohit\'s Workspace'}})

print("Finished rewriting old properties safely!")
