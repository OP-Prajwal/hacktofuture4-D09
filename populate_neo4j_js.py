
import os
import sys
from pathlib import Path

# Add backend to sys.path
backend_path = Path("backend").resolve()
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.cig.orchestrator import analyze_repository

def main():
    workspace = "default"
    project_name = "test-js-repo" # NEW PROJECT!
    repo_path = str(Path("test-js-repo").resolve())
    
    print(f"Populating Neo4j for {workspace}/{project_name} at {repo_path}...")
    
    # force=True to ensure we index it fresh
    result = analyze_repository(workspace, project_name, local_path=repo_path, force=True)
    
    if result.get("status") == "success":
        print("\n✅ SUCCESS: Neo4j populated for " + project_name)
    else:
        print("\n❌ FAILED: Neo4j population failed.")

if __name__ == "__main__":
    main()
