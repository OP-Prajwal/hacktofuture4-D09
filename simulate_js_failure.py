
import os
import sys
import subprocess
from pathlib import Path

# Add backend to sys.path
backend_path = Path("backend").resolve()
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.auto_healer import trigger_auto_heal

def create_broken_js():
    """Creates a broken JS file in test-js-repo."""
    broken_code = """
function greet(user) {
    // BUG: Accessing property of undefined
    console.log("Hello, " + user.profile.name);
}

// Simulate production crash
console.log("App starting...");
try {
    greet(null); // This will crash
} catch (e) {
    console.error(e.stack);
    process.exit(1);
}
"""
    repo_path = Path("test-js-repo")
    file_path = repo_path / "broken_app.js"
    with open(file_path, "w") as f:
        f.write(broken_code)
    return file_path

def main():
    broken_file = create_broken_js()
    repo_root = str(Path("test-js-repo").resolve())
    
    # Run and fail
    print(f"--- Running {broken_file} ---")
    result = subprocess.run(["node", str(broken_file)], capture_output=True, text=True)
    
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    
    if result.returncode != 0:
        print("\n[Sim JS] Triggering Orchestrator for JS repo...")
        diagnosis = trigger_auto_heal(
            workspace="default",
            project="test-js-repo",
            logs=result.stdout.splitlines(),
            error_lines=result.stderr.splitlines(),
            exit_code=result.returncode,
            repo_root=repo_root
        )
        
        print("\n--- Orchestrator Diagnosis (JS Repo) ---")
        import json
        print(json.dumps(diagnosis, indent=2))
        
        if any("broken_app.js" in loc["path"] for loc in diagnosis.get("code_locations", [])):
            print("\n✅ SUCCESS: Orchestrator correctly identified the JS repo context!")
        else:
            print("\n❌ FAILED: Orchestrator did not find JS repo nodes.")

if __name__ == "__main__":
    main()
