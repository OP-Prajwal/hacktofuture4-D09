from db.mongo import mongo
from datetime import datetime
import re
import uuid

def create_project(workspace_name: str, name: str, description: str):
    projects = mongo.get_collection("projects")
    project_id = str(uuid.uuid4())[:8]  # internal DB record ID only
    # Slugs deprecated. Verbatim name mapping.
    clone_code = f"{workspace_name}/{name}"
    
    project_doc = {
        "id": project_id,
        "workspace": workspace_name,
        "name": name,
        "description": description,
        "cloneCode": clone_code,
        "members": [],
        "created_at": datetime.utcnow()
    }
    
    projects.insert_one(project_doc)
    # Remove _id before returning to frontend
    project_doc.pop("_id", None)
    return project_doc

def get_workspace_projects(workspace_name: str):
    projects = mongo.get_collection("projects")
    results = list(projects.find({"workspace": workspace_name}, {"_id": 0}).sort("created_at", -1))
    return results

def add_project_member(workspace_name: str, project_id: str, name: str, email: str, role: str):
    projects = mongo.get_collection("projects")
    projects.update_one(
        {"workspace": workspace_name, "id": project_id},
        {"$push": {"members": {"name": name, "email": email, "role": role}}}
    )
    return True
    
def remove_project_member(workspace_name: str, project_id: str, member_email: str):
    projects = mongo.get_collection("projects")
    projects.update_one(
        {"workspace": workspace_name, "id": project_id},
        {"$pull": {"members": {"email": member_email}}}
    )
    return True
