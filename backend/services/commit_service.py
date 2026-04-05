from db.mongo import mongo
from datetime import datetime


def create_commit(workspace: str, project: str, manifest: list[dict], metadata: dict) -> str:
    """
    Create a commit (snapshot) document in MongoDB.

    manifest: list of { path: str, hash: str, size: int, extension: str }
    metadata: arbitrary extra info (e.g. total_files, push_source)

    Returns the commit_id (str).
    """
    commits = mongo.get_collection("commits")

    commit_doc = {
        "workspace": workspace,
        "project": project,
        "remote": f"{workspace}/{project}",
        "manifest": manifest,
        "total_files": len(manifest),
        "metadata": metadata,
        "pushed_at": datetime.utcnow(),
        "status": "complete"
    }

    result = commits.insert_one(commit_doc)
    return str(result.inserted_id)


def get_commits(workspace: str, project: str, limit: int = 20) -> list[dict]:
    """Return the latest commits for a project."""
    commits = mongo.get_collection("commits")
    cursor = commits.find(
        {"workspace": workspace, "project": project},
        {"_id": 0},
        sort=[("pushed_at", -1)],
        limit=limit
    )
    return list(cursor)
