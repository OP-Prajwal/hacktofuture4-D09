import json
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from db.mongo import mongo
from db.neo4j_db import neo4j_db
from services.project_service import ProjectPushRequest, build_project_graph_from_payload
from services.blob_service import has_blob, stream_blob_to_gridfs, get_blob_info, is_text_file
from services.commit_service import create_commit, get_commits, get_latest_tree
from services.auth_service import register_user, login_user, decode_access_token
from services.project_db_service import create_project, get_workspace_projects, add_project_member, remove_project_member

app = FastAPI(title="NEXUS-X Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

# ─── Auth Routes ─────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    type: str # individual or enterprise
    name: str # user name
    email: str
    password: str
    company: str = "" # only used if type == enterprise
    role: str = "admin"

@app.post("/api/auth/register")
def register(body: RegisterRequest):
    try:
        res = register_user(body.type, body.email, body.password, body.name, body.company, body.role)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/api/auth/login")
def login(body: LoginRequest):
    try:
        res = login_user(body.email, body.password)
        return res
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

# ─── DB Project Routes ───────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    name: str
    description: str

@app.post("/api/workspaces/{workspace_slug}/projects")
def add_project(workspace_slug: str, body: CreateProjectRequest, current_user: dict = Depends(get_current_user)):
    if current_user.get("workspace") != workspace_slug:
        raise HTTPException(status_code=403, detail="Not authorized for this workspace")
    project = create_project(workspace_slug, body.name, body.description)
    return project

@app.get("/api/workspaces/{workspace_slug}/projects")
def get_projects(workspace_slug: str, current_user: dict = Depends(get_current_user)):
    if current_user.get("workspace") != workspace_slug:
        raise HTTPException(status_code=403, detail="Not authorized for this workspace")
    return get_workspace_projects(workspace_slug)

class AddMemberRequest(BaseModel):
    name: str
    email: str
    role: str

@app.post("/api/workspaces/{workspace_slug}/projects/{project_id}/members")
def add_member(workspace_slug: str, project_id: str, body: AddMemberRequest, current_user: dict = Depends(get_current_user)):
    add_project_member(workspace_slug, project_id, body.name, body.email, body.role)
    return {"status": "ok"}

@app.delete("/api/workspaces/{workspace_slug}/projects/{project_id}/members/{email}")
def remove_member(workspace_slug: str, project_id: str, email: str, current_user: dict = Depends(get_current_user)):
    remove_project_member(workspace_slug, project_id, email)
    return {"status": "ok"}


# ─── Existing graph push ──────────────────────────────────────────────────────

@app.post("/api/repo/{workspace}/{project_name}/push")
def push_project(workspace: str, project_name: str, payload: ProjectPushRequest):
    try:
        result = build_project_graph_from_payload(workspace, project_name, payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Git-like streaming blob transfer ────────────────────────────────────────

class PreflightRequest(BaseModel):
    hashes: List[str]

class PreflightResponse(BaseModel):
    missing: List[str]


@app.post("/api/repo/{workspace}/{project_name}/preflight",
          response_model=PreflightResponse)
def preflight(workspace: str, project_name: str, body: PreflightRequest):
    """
    Delta check — client sends all intended hashes, server returns only
    the ones it doesn't already have in GridFS.
    Equivalent to git's 'have/want' negotiation.
    """
    missing = [h for h in body.hashes if not has_blob(h)]
    return {"missing": missing}


@app.post("/api/repo/{workspace}/{project_name}/blob/{file_hash}")
async def upload_blob_stream(
    workspace: str,
    project_name: str,
    file_hash: str,
    request: Request
):
    """
    True binary streaming upload.
    
    The CLI sends raw file bytes via HTTP chunked-transfer-encoding.
    This endpoint reads the stream iteratively and writes each chunk
    directly into MongoDB GridFS — nothing is buffered in full memory.
    
    File metadata is passed via X-Nexus-Meta header as JSON.
    """
    # Skip if already stored (idempotent)
    if has_blob(file_hash):
        return {"status": "exists", "hash": file_hash}

    # Parse metadata from request header
    meta_raw = request.headers.get("x-nexus-meta", "{}")
    try:
        meta = json.loads(meta_raw)
    except json.JSONDecodeError:
        meta = {}

    try:
        await stream_blob_to_gridfs(file_hash, request.stream(), meta)
        return {"status": "stored", "hash": file_hash}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/repo/{workspace}/{project_name}/blob/{file_hash}")
def get_blob(workspace: str, project_name: str, file_hash: str):
    """Returns metadata for a stored blob (no content)."""
    info = get_blob_info(file_hash)
    if not info:
        raise HTTPException(status_code=404, detail="Blob not found")
    return info


class ManifestFile(BaseModel):
    path: str
    hash: str
    size: int
    extension: str

class CommitBody(BaseModel):
    manifest: List[ManifestFile]
    metadata: dict = {}


@app.post("/api/repo/{workspace}/{project_name}/commit")
def push_commit(workspace: str, project_name: str, body: CommitBody):
    """
    Creates a commit (snapshot) record in MongoDB.
    Final step of `nexus push` — records which hashes make up this snapshot.
    """
    try:
        manifest_dicts = [f.model_dump() for f in body.manifest]
        commit_id = create_commit(workspace, project_name, manifest_dicts, body.metadata)
        return {
            "status": "committed",
            "commit_id": commit_id,
            "total_files": len(body.manifest)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/repo/{workspace}/{project_name}/commits")
def list_commits(workspace: str, project_name: str, limit: int = 20):
    return {"commits": get_commits(workspace, project_name, limit)}


@app.get("/api/repo/{workspace}/{project_name}/tree")
def get_file_tree(workspace: str, project_name: str):
    """
    Returns the nested file tree from the most recent nexus push.
    The tree is built from the commit manifest stored in MongoDB.
    """
    tree = get_latest_tree(workspace, project_name)
    if not tree:
        return {"status": "no_push", "tree": None}
    return {"status": "ok", **tree}


# ─── Health / test routes ─────────────────────────────────────────────────────

@app.get("/test-mongo")
def test_mongo():
    logs = mongo.get_collection("logs")
    logs.insert_one({"msg": "mongo connected"})
    return {"status": "mongo ok"}

@app.get("/test-neo4j")
def test_neo4j():
    result = neo4j_db.run_query("RETURN 'neo4j connected' AS msg")
    return result
