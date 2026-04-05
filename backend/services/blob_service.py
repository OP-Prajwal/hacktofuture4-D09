import os
import json
import gridfs
from db.mongo import mongo
from datetime import datetime

# Extensions to skip — binaries, compiled artifacts, media, etc.
BINARY_EXTENSIONS = {
    '.pyc', '.pyo', '.pyd', '.class', '.o', '.obj', '.a', '.lib', '.so', '.dll', '.exe',
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.whl', '.egg',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp', '.tiff',
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
    '.mp3', '.mp4', '.wav', '.ogg', '.avi', '.mov', '.mkv', '.webm',
    '.db', '.sqlite', '.sqlite3', '.parquet', '.pkl', '.npy', '.npz',
    '.bin', '.dat', '.img', '.iso', '.pdf', '.lock'
}

def is_text_file(extension: str) -> bool:
    return extension.lower() not in BINARY_EXTENSIONS


def _get_gridfs() -> gridfs.GridFS:
    """Return a GridFS instance scoped to the 'blobs' bucket."""
    return gridfs.GridFS(mongo.db, collection="blobs")


def has_blob(file_hash: str) -> bool:
    """
    Check if a blob with this SHA-256 hash already exists in GridFS.
    Uses the filename field as the content-addressable key.
    """
    fs = _get_gridfs()
    return fs.exists({"filename": file_hash})


async def stream_blob_to_gridfs(file_hash: str, request_stream, meta: dict):
    """
    Stream raw bytes from an HTTP request body directly into MongoDB GridFS.
    
    GridFS internally chunks the binary into 255KB pieces — nothing is 
    loaded entirely into memory on the backend side.
    
    request_stream: async iterable of bytes (FastAPI Request.stream())
    meta: { name, extension, size }
    """
    fs = _get_gridfs()

    with fs.new_file(
        filename=file_hash,
        metadata={
            "name":      meta.get("name", ""),
            "extension": meta.get("extension", ""),
            "size":      meta.get("size", 0),
            "uploaded_at": datetime.utcnow().isoformat()
        }
    ) as grid_file:
        async for chunk in request_stream:
            grid_file.write(chunk)


def get_blob_info(file_hash: str) -> dict | None:
    """Return metadata for a stored blob (without content)."""
    fs = _get_gridfs()
    grid_out = fs.find_one({"filename": file_hash})
    if not grid_out:
        return None
    return {
        "hash":      file_hash,
        "name":      grid_out.metadata.get("name"),
        "extension": grid_out.metadata.get("extension"),
        "size":      grid_out.metadata.get("size"),
        "length":    grid_out.length,
        "upload_id": str(grid_out._id)
    }
