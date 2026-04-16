import json
from fastapi import FastAPI, HTTPException, Request, Depends, Response, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from db.mongo import mongo
from services.project_service import ProjectPushRequest, build_project_graph_from_payload
from services.blob_service import has_blob, stream_blob_to_gridfs, get_blob_info, is_text_file
from services.commit_service import create_commit, get_commits, get_latest_tree
from services.auth_service import register_user, login_user, decode_access_token
from services.project_db_service import create_project, get_workspace_projects, add_project_member, remove_project_member
from services.cig import analyze_repository, get_project_graph, ask_repository

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


@app.get("/api/repo/{workspace}/{project_name}/blob/{file_hash}/content")
def get_blob_content_endpoint(workspace: str, project_name: str, file_hash: str):
    """Returns actual binary content of a stored blob."""
    from services.blob_service import get_blob_content
    content = get_blob_content(file_hash)
    if not content:
        raise HTTPException(status_code=404, detail="Blob not found")
    return Response(content=content)


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
    Final step of `nexus push`.
    NOW: Automatically triggers background analysis so the LLM knows the repo instantly.
    """
    try:
        manifest_dicts = [f.model_dump() for f in body.manifest]
        commit_id = create_commit(workspace, project_name, manifest_dicts, body.metadata)
        
        # ─── AUTO-TRIGGER ANALYSIS ───
        # This starts the LLM "learning" phase in the background immediately
        try:
            start_analysis_async(workspace, project_name, force=False)
        except Exception as e:
            print(f"[AUTO-ANALYSIS] Failed to trigger: {e}")

        return {
            "status": "committed",
            "commit_id": commit_id,
            "total_files": len(body.manifest),
            "auto_analysis": "triggered"
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


# ─── Code Intelligence Graph (CIG) Routes ────────────────────────────────────

from services.cig import start_analysis_async, get_analysis_status

class AnalyzeRequest(BaseModel):
    local_path: Optional[str] = None
    force: bool = False

@app.post("/api/repo/{workspace}/{project_name}/analyze")
def analyze_project(workspace: str, project_name: str, body: AnalyzeRequest = None):
    """
    Start CIG analysis in background. Returns immediately with a job_id.
    Poll /analyze/status/{job_id} for progress.
    """
    try:
        local_path = body.local_path if body else None
        force = body.force if body else False
        result = start_analysis_async(workspace, project_name, local_path=local_path, force=force)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/repo/{workspace}/{project_name}/analyze/status/{job_id}")
def analyze_status(workspace: str, project_name: str, job_id: str):
    """Poll this endpoint for analysis progress."""
    return get_analysis_status(job_id)


@app.get("/api/repo/{workspace}/{project_name}/graph")
def get_graph(workspace: str, project_name: str):
    """Return the full knowledge graph as JSON for visualization."""
    try:
        result = get_project_graph(workspace, project_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class QueryRequest(BaseModel):
    question: str

@app.post("/api/repo/{workspace}/{project_name}/query")
def query_project(workspace: str, project_name: str, body: QueryRequest):
    """Query the knowledge graph with natural language."""
    try:
        result = ask_repository(workspace, project_name, body.question)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── Blast Radius API ─────────────────────────────────────────────────────────

from services.cig.locator import locate_incident_nodes

class LocateRequest(BaseModel):
    search_terms: List[str]
    file_hints: List[str]
    symbol_hints: List[str]

@app.post("/api/repo/{workspace}/{project_name}/locate")
def locate_incident(workspace: str, project_name: str, body: LocateRequest):
    try:
        project_path = f"{workspace}/{project_name}"
        return locate_incident_nodes(project_path, body.search_terms, body.file_hints, body.symbol_hints)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from services.cig.blast_radius import calculate_blast_radius

class BlastRadiusRequest(BaseModel):
    changed_files: List[str]

@app.post("/api/repo/{workspace}/{project_name}/blast-radius")
def blast_radius(workspace: str, project_name: str, body: BlastRadiusRequest):
    """Calculate the blast radius of changed files using the knowledge graph."""
    try:
        project_path = f"{workspace}/{project_name}"
        result = calculate_blast_radius(project_path, body.changed_files)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── WebSocket — Live CI/CD Terminal ──────────────────────────────────────────

from services.runner_hub import runner_hub

@app.websocket("/ws/runner/{workspace}/{project_name}")
async def ws_runner(websocket: WebSocket, workspace: str, project_name: str):
    """WebSocket endpoint for CI/CD runners to stream logs."""
    await runner_hub.connect_runner(websocket, workspace, project_name)
    try:
        while True:
            data = await websocket.receive_json()
            await runner_hub.handle_runner_message(workspace, project_name, data)
    except WebSocketDisconnect:
        await runner_hub.disconnect_runner(workspace, project_name)
    except Exception:
        await runner_hub.disconnect_runner(workspace, project_name)


@app.websocket("/ws/viewer/{workspace}/{project_name}")
async def ws_viewer(websocket: WebSocket, workspace: str, project_name: str):
    """WebSocket endpoint for dashboard viewers to watch live logs."""
    await runner_hub.connect_viewer(websocket, workspace, project_name)
    try:
        while True:
            # Viewers can send commands (e.g., request log replay)
            data = await websocket.receive_text()
            # For now, just keep the connection alive
    except WebSocketDisconnect:
        await runner_hub.disconnect_viewer(websocket, workspace, project_name)
    except Exception:
        await runner_hub.disconnect_viewer(websocket, workspace, project_name)


@app.get("/api/repo/{workspace}/{project_name}/runner/status")
def get_runner_status(workspace: str, project_name: str):
    """Get the current CI/CD runner status for a project."""
    return runner_hub.get_status(workspace, project_name)


# ─── HTTP Log Ingestion (fallback when WebSocket isn't available) ─────────────

class LogBatch(BaseModel):
    logs: List[dict]
    exit_code: Optional[int] = None

@app.post("/api/repo/{workspace}/{project_name}/logs")
async def ingest_logs(workspace: str, project_name: str, body: LogBatch):
    """
    HTTP fallback for log ingestion when WebSocket isn't available.
    Stores logs in MongoDB and replays them to any connected Dashboard viewers.
    """
    session = runner_hub.get_session(workspace, project_name)

    for entry in body.logs:
        log_entry = {
            "type": "log",
            "line": entry.get("line", ""),
            "stream": entry.get("stream", "stdout"),
            "timestamp": entry.get("ts", 0) / 1000
        }
        session.logs.append(log_entry)
        await runner_hub._broadcast_to_viewers(session, log_entry)

    if body.exit_code is not None:
        session.exit_code = body.exit_code
        session.status = "success" if body.exit_code == 0 else "failed"
        
        # Trigger the Orchestrator if the process crashed!
        if body.exit_code != 0:
            print(f"[HTTP Logs] Received exit code {body.exit_code}! Triggering Orchestrator...")
            await runner_hub._on_ci_failure(session)

    logs_col = mongo.get_collection("runtime_logs")
    logs_col.insert_one({
        "workspace": workspace,
        "project": project_name,
        "logs": body.logs,
        "exit_code": body.exit_code,
        "total_lines": len(body.logs),
    })

    return {
        "status": "ok",
        "lines_ingested": len(body.logs),
        "session_status": session.status
    }

@app.get("/api/repo/{workspace}/{project_name}/logs")
def get_logs(workspace: str, project_name: str, limit: int = 200):
    """Retrieve recent runtime logs for a project."""
    session = runner_hub.get_session(workspace, project_name)
    if session.logs:
        return {
            "status": session.status,
            "exit_code": session.exit_code,
            "total": len(session.logs),
            "logs": session.logs[-limit:]
        }

    logs_col = mongo.get_collection("runtime_logs")
    doc = logs_col.find_one(
        {"workspace": workspace, "project": project_name},
        sort=[("_id", -1)]
    )
    if doc:
        return {
            "status": "historical",
            "exit_code": doc.get("exit_code"),
            "total": doc.get("total_lines", 0),
            "logs": doc.get("logs", [])[-limit:]
        }

    return {"status": "no_logs", "logs": [], "total": 0}


# ─── Incident Reports API ────────────────────────────────────────────────────

@app.get("/api/repo/{workspace}/{project_name}/incidents")
def list_incidents(workspace: str, project_name: str, limit: int = 20):
    """List all forensic incident reports for a project."""
    reports_col = mongo.get_collection("incident_reports")
    docs = list(reports_col.find(
        {"workspace": workspace, "project": project_name},
        {"_id": 0, "report_markdown": 0}  # Exclude heavy fields from list
    ).sort("created_at", -1).limit(limit))

    return {"incidents": docs, "total": len(docs)}


@app.get("/api/repo/{workspace}/{project_name}/incidents/{incident_id}")
def get_incident(workspace: str, project_name: str, incident_id: str):
    """Get a specific forensic incident report with full markdown."""
    reports_col = mongo.get_collection("incident_reports")
    doc = reports_col.find_one(
        {"workspace": workspace, "project": project_name, "incident_id": incident_id},
        {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Incident report not found")
    return doc


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
