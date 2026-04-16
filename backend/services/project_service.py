import os
from typing import List
from pydantic import BaseModel
from db.mongo import mongo

class FileNode(BaseModel):
    path: str
    name: str
    size: int
    extension: str

class ProjectPushRequest(BaseModel):
    project_name: str
    files: List[FileNode]

def build_project_graph_from_payload(workspace: str, project_name: str, payload: ProjectPushRequest):
    virtual_project_path = f"{workspace}/{project_name}"
    
    nodes_created = 0
    files_processed = []
    
    print(f"\n[VERIFICATION LOG] Stub graph create logic for {virtual_project_path}")
    
    for file_node in payload.files:
        files_processed.append(file_node.path)
        nodes_created += 1
            
    return {"status": "success", "nodes_created": nodes_created, "project": project_name, "files_processed": files_processed}
