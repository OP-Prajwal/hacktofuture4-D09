import os
from typing import List
from pydantic import BaseModel
from db.neo4j_db import neo4j_db

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
    
    project_query = """
    MERGE (p:Project {workspace: $workspace, name: $name, path: $path})
    RETURN p
    """
    project_params = {"workspace": workspace, "name": project_name, "path": virtual_project_path}
    
    try:
        neo4j_db.run_query(project_query, project_params)
        nodes_created += 1
    except Exception as e:
        print(f"\n[VERIFICATION LOG] Neo4j Offline! The following query would have run:\n{project_query}")
        print(f"Parameters: {project_params}\n")
    
    for file_node in payload.files:
        files_processed.append(file_node.path)
        
        file_query = """
        MATCH (p:Project {path: $project_path})
        MERGE (f:File {path: $file_path})
        SET f.name = $name, f.extension = $ext, f.size = $size
        MERGE (p)-[:CONTAINS]->(f)
        """
        file_params = {
            "project_path": virtual_project_path,
            "file_path": file_node.path,
            "name": file_node.name,
            "ext": file_node.extension,
            "size": file_node.size
        }
        
        try:
            neo4j_db.run_query(file_query, file_params)
            nodes_created += 1
        except Exception:
            print(f"[VERIFICATION LOG] File Query for {file_node.name}:\n{file_query}")
            print(f"Parameters: {file_params}\n")
            
    return {"status": "success", "nodes_created": nodes_created, "project": project_name, "files_processed": files_processed}

