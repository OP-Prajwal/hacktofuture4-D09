
import os
import sys
import subprocess
from pathlib import Path

# Add backend to sys.path to import auto_healer
backend_path = Path("backend").resolve()
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.auto_healer import trigger_auto_heal

def create_broken_code():
    """Creates a broken python file in test-repo."""
    broken_code = """
def calculate_total(items):
    total = 0
    for item in items:
        # BUG: This will fail if item['price'] is missing or None
        total += item['price']
    return total

if __name__ == "__main__":
    # Simulate a production-like crash
    print("Starting payment processing...")
    cart = [
        {"name": "Laptop", "price": 1200},
        {"name": "Mouse", "price": None}, # This will trigger a TypeError
    ]
    print(f"Processing {len(cart)} items")
    result = calculate_total(cart)
    print(f"Total: {result}")
"""
    repo_path = Path("test-repo")
    repo_path.mkdir(exist_ok=True)
    file_path = repo_path / "broken_service.py"
    with open(file_path, "w") as f:
        f.write(broken_code)
    return file_path

def run_broken_code(file_path):
    """Runs the broken code and captures logs/errors."""
    print(f"--- Running {file_path} ---")
    result = subprocess.run(
        [sys.executable, str(file_path)],
        capture_output=True,
        text=True
    )
    
    logs = result.stdout.splitlines()
    error_lines = result.stderr.splitlines()
    
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    
    return logs, error_lines, result.returncode

def main():
    # 1. Setup broken environment
    broken_file = create_broken_code()
    repo_root = str(Path("test-repo").resolve())
    
    # 2. Execute and fail
    logs, error_lines, exit_code = run_broken_code(broken_file)
    
    if exit_code != 0:
        print("\n[Sim] Failure detected! Triggering Nexus-X Orchestrator...")
        
        # 3. Trigger the Orchestrator (Auto-Healer)
        # Note: We now pass the repo_root so the project name is resolved dynamically
        diagnosis = trigger_auto_heal(
            workspace="default",
            project="test-repo",
            logs=logs,
            error_lines=error_lines,
            exit_code=exit_code,
            repo_root=repo_root
        )
        
        print("\n--- Orchestrator Diagnosis ---")
        import json
        print(json.dumps(diagnosis, indent=2))
        
        if diagnosis.get("status") == "analyzed":
            print("\n✅ SUCCESS: Orchestrator analyzed the failure.")
        else:
            print("\n⚠️ WARNING: Orchestrator used fallback mode. Check if dependencies are installed.")
    else:
        print("❌ FAILED: The broken code didn't actually fail.")

if __name__ == "__main__":
    main()
