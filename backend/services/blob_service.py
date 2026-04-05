from db.mongo import mongo
from datetime import datetime

# Extensions to skip — binaries, compiled artifacts, media, etc.
BINARY_EXTENSIONS = {
    # Compiled / bytecode
    '.pyc', '.pyo', '.pyd', '.class', '.o', '.obj', '.a', '.lib', '.so', '.dll', '.exe',
    # Archives
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.whl', '.egg',
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp', '.tiff',
    # Fonts / media
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
    '.mp3', '.mp4', '.wav', '.ogg', '.avi', '.mov', '.mkv', '.webm',
    # Data / DB
    '.db', '.sqlite', '.sqlite3', '.parquet', '.pkl', '.npy', '.npz',
    # Misc binary
    '.bin', '.dat', '.img', '.iso', '.pdf', '.lock'
}

def is_text_file(extension: str) -> bool:
    """Return True if the file extension is a known text/source type."""
    return extension.lower() not in BINARY_EXTENSIONS


def has_blob(file_hash: str) -> bool:
    """Check if a fully assembled blob already exists in MongoDB."""
    blobs = mongo.get_collection("blobs")
    return blobs.find_one({"hash": file_hash, "status": "complete"}) is not None


def store_blob_chunk(file_hash: str, chunk_index: int, chunk_data: str, total_chunks: int):
    """
    Store a single chunk of a blob. Chunks are accumulated in a
    separate 'blob_chunks' collection until finalized.
    """
    chunks = mongo.get_collection("blob_chunks")
    chunks.update_one(
        {"hash": file_hash, "chunk_index": chunk_index},
        {"$set": {
            "hash": file_hash,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "data": chunk_data,
            "created_at": datetime.utcnow()
        }},
        upsert=True
    )


def finalize_blob(file_hash: str, total_chunks: int, meta: dict):
    """
    Assemble all stored chunks into a single blob document.
    Cleans up the temporary chunk records afterwards.
    """
    chunks_col = mongo.get_collection("blob_chunks")
    blobs_col = mongo.get_collection("blobs")

    # Fetch all chunks for this hash, ordered
    raw_chunks = list(chunks_col.find(
        {"hash": file_hash},
        sort=[("chunk_index", 1)]
    ))

    if len(raw_chunks) != total_chunks:
        raise ValueError(
            f"Chunk mismatch for {file_hash}: expected {total_chunks}, got {len(raw_chunks)}"
        )

    # Reassemble content
    full_content = "".join(c["data"] for c in raw_chunks)

    blobs_col.update_one(
        {"hash": file_hash},
        {"$set": {
            "hash": file_hash,
            "content": full_content,
            "size": meta.get("size", 0),
            "extension": meta.get("extension", ""),
            "name": meta.get("name", ""),
            "status": "complete",
            "created_at": datetime.utcnow()
        }},
        upsert=True
    )

    # Clean up temporary chunks
    chunks_col.delete_many({"hash": file_hash})


def get_blob(file_hash: str) -> dict | None:
    """Retrieve a complete blob by its hash."""
    blobs = mongo.get_collection("blobs")
    return blobs.find_one({"hash": file_hash, "status": "complete"}, {"_id": 0})
