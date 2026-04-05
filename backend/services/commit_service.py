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


def _build_tree(manifest: list[dict]) -> dict:
    """
    Convert a flat list of { path, hash, size, extension } entries into
    a nested tree structure suitable for rendering in the frontend.

    Output shape:
    {
      "type": "dir",
      "name": "root",
      "children": [
        { "type": "dir", "name": "src", "children": [...] },
        { "type": "file", "name": "README.md", "hash": "...", "size": 1234, "extension": ".md" }
      ]
    }
    """
    root: dict = {"type": "dir", "name": "root", "children": []}

    for entry in manifest:
        parts = entry["path"].replace("\\", "/").split("/")
        node = root
        # Walk/create directory nodes
        for part in parts[:-1]:
            existing = next((c for c in node["children"] if c["name"] == part and c["type"] == "dir"), None)
            if not existing:
                existing = {"type": "dir", "name": part, "children": []}
                node["children"].append(existing)
            node = existing
        # Add the file leaf
        filename = parts[-1]
        node["children"].append({
            "type":      "file",
            "name":      filename,
            "hash":      entry.get("hash", ""),
            "size":      entry.get("size", 0),
            "extension": entry.get("extension", "")
        })

    # Sort: dirs first, then files, both alphabetically
    def sort_node(n: dict):
        if "children" in n:
            n["children"].sort(key=lambda x: (0 if x["type"] == "dir" else 1, x["name"].lower()))
            for child in n["children"]:
                sort_node(child)
    sort_node(root)
    return root


def get_latest_tree(workspace: str, project: str) -> dict | None:
    """
    Returns the nested file tree from the most recent push commit.
    Returns None if no commit exists yet.
    """
    commits = mongo.get_collection("commits")
    latest = commits.find_one(
        {"workspace": workspace, "project": project},
        sort=[("pushed_at", -1)]
    )
    if not latest or not latest.get("manifest"):
        return None

    return {
        "commit_id":  str(latest["_id"]),
        "pushed_at":  latest["pushed_at"].isoformat(),
        "total_files": latest["total_files"],
        "tree": _build_tree(latest["manifest"])
    }

