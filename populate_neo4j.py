
import os
import sys
from pathlib import Path

# Add backend to sys.path
backend_path = Path("backend").resolve()
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Mock MongoDB if needed, but since we have a real one (from .env), it should work
from services.cig.orchestrator import analyze_repository

def main():
    workspace = "default"
    project_name = "test-repo"
    # The path to our test-repo
    repo_path = str(Path("test-repo").resolve())
    
    print(f"Populating Neo4j for {workspace}/{project_name} at {repo_path}...")
    
    # force=False means it will use the existing .gitnexus/lbug we just created
    result = analyze_repository(workspace, project_name, local_path=repo_path, force=False)
    
    if result.get("status") == "success":
        print("\n✅ SUCCESS: Neo4j populated!")
        print(f"Nodes: {result['graph']['nodes']}, Edges: {result['graph']['edges']}")
        print(f"Neo4j Stats: {result.get('neo4j')}")
    else:
        print("\n❌ FAILED: Neo4j population failed.")
        print(f"Message: {result.get('message')}")

if __name__ == "__main__":
    main()
