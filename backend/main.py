from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from db.mongo import mongo
from db.neo4j_db import neo4j_db
from services.project_service import ProjectPushRequest, build_project_graph_from_payload
from services.blob_service import has_blob, store_blob_chunk, finalize_blob, is_text_file
from services.commit_service import create_commit, get_commits

app = FastAPI(title="NEXUS-X Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Existing graph push ──────────────────────────────────────────────────────

@app.post("/api/repo/{workspace}/{project_name}/push")
def push_project(workspace: str, project_name: str, payload: ProjectPushRequest):
    try:
        result = build_project_graph_from_payload(workspace, project_name, payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Git-like Blob Transfer ───────────────────────────────────────────────────

class PreflightRequest(BaseModel):
    hashes: List[str]  # SHA-256 hashes of all files the client wants to push

class PreflightResponse(BaseModel):
    missing: List[str]  # Hashes the server does NOT already have


@app.post("/api/repo/{workspace}/{project_name}/preflight",
          response_model=PreflightResponse)
def preflight(workspace: str, project_name: str, body: PreflightRequest):
    """
    Client sends all file hashes it intends to push.
    Server responds with only the hashes it doesn't already have stored.
    This is the delta-check — like 'git push' skipping already-known objects.
    """
    missing = [h for h in body.hashes if not has_blob(h)]
    return {"missing": missing}


class BlobChunkBody(BaseModel):
    data: str          # base64-encoded chunk content
    total_chunks: int  # total number of chunks for this blob


@app.post("/api/repo/{workspace}/{project_name}/blob/{file_hash}/chunk/{chunk_index}")
def upload_blob_chunk(
    workspace: str,
    project_name: str,
    file_hash: str,
    chunk_index: int,
    body: BlobChunkBody
):
    """
    Receives one chunk of a file blob.
    Chunks are stored temporarily until finalize is called.
    """
    try:
        store_blob_chunk(file_hash, chunk_index, body.data, body.total_chunks)
        return {"status": "ok", "hash": file_hash, "chunk": chunk_index}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class BlobFinalizeBody(BaseModel):
    total_chunks: int
    size: int
    extension: str
    name: str


@app.post("/api/repo/{workspace}/{project_name}/blob/{file_hash}/finalize")
def finalize_blob_upload(
    workspace: str,
    project_name: str,
    file_hash: str,
    body: BlobFinalizeBody
):
    """
    Assembles stored chunks into a complete blob document in MongoDB.
    """
    try:
        finalize_blob(file_hash, body.total_chunks, {
            "size": body.size,
            "extension": body.extension,
            "name": body.name
        })
        return {"status": "stored", "hash": file_hash}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    This is the final step of `nexus push` — like 'git commit' after staging.
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
    """Returns recent push history for a project."""
    return {"commits": get_commits(workspace, project_name, limit)}


# ─── Test routes ─────────────────────────────────────────────────────────────

@app.get("/test-mongo")
def test_mongo():
    logs = mongo.get_collection("logs")
    logs.insert_one({"msg": "mongo connected"})
    return {"status": "mongo ok"}

@app.get("/test-neo4j")
def test_neo4j():
    result = neo4j_db.run_query("RETURN 'neo4j connected' AS msg")
    return result
