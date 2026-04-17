import os
import sys
import json
import requests
import subprocess
from typing import List, Dict

# Try to import yaml, but provide a fallback if not installed
try:
    import yaml
except ImportError:
    yaml = None

def get_changed_files() -> List[str]:
    """Get list of files changed in this PR or commit."""
    try:
        # Check if we are in a git repo
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], check=True, capture_output=True)
        
        # Get changed files compared to main/master or previous commit
        base_ref = os.getenv("GITHUB_BASE_REF") or "HEAD~1"
        cmd = ["git", "diff", "--name-only", base_ref]
        result = subprocess.run(cmd, capture_output=True, text=True)
        files = result.stdout.strip().split("\n")
        return [f for f in files if f and os.path.exists(f) and f.endswith(('.py', '.js', '.ts', '.tsx', '.go'))]
    except Exception as e:
        print(f"⚠️ Warning: Could not determine changed files via git: {e}")
        return []

def load_code_contract() -> List[str]:
    """Load business logic rules from nexus-rules.yml."""
    contract_path = "nexus-rules.yml"
    if not os.path.exists(contract_path):
        print("ℹ️ No nexus-rules.yml found. Using default AI rules.")
        return []
    
    if yaml is None:
        print("⚠️ PyYAML not installed. Cannot parse nexus-rules.yml. Run: pip install pyyaml")
        return []

    try:
        with open(contract_path, "r") as f:
            data = yaml.safe_load(f)
            rules = data.get("rules", [])
            return [f"{r.get('category')}: {r.get('rule')} (Severity: {r.get('severity')})" for r in rules]
    except Exception as e:
        print(f"⚠️ Error parsing nexus-rules.yml: {e}")
        return []

def post_github_comment(details: List[Dict]):
    """Posts AI findings as comments on the GitHub PR."""
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    pr_number = os.getenv("GITHUB_PR_NUMBER")
    
    if not token or not repo or not pr_number:
        return

    print(f"💬 Posting findings to PR #{pr_number}...")
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Unified summary comment
    summary = "### 🤖 Nexus-X AI Analysis Report\n"
    if not details:
        summary += "✅ No business logic or security violations detected."
    else:
        summary += f"⚠️ Found {len(details)} violations of your Code Contract.\n\n"
        for d in details[:5]: # Top 5
            severity_icon = "🔴" if d.get('severity') in ['HIGH', 'CRITICAL'] else "🟡"
            summary += f"- {severity_icon} **{d.get('rule')}**: {d.get('message')} (`{d.get('file')}:{d.get('line', 'N/A')}`)\n"
            if d.get('suggestion'):
                summary += f"  - 💡 *Suggestion: {d.get('suggestion')}*\n"
            
    comment_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    try:
        requests.post(comment_url, headers=headers, json={"body": summary})
    except Exception as e:
        print(f"⚠️ Failed to post GitHub comment: {e}")

def run_analysis():
    api_url = os.getenv("NEXUS_API_URL")
    if not api_url:
        print("❌ Error: NEXUS_API_URL environment variable not set.")
        sys.exit(1)

    if not api_url.endswith("/analyze"):
        api_url = f"{api_url.rstrip('/')}/analyze"

    print(f"🚀 Starting Nexus AI Code Analysis...")
    
    contract_rules = load_code_contract()
    changed_files = get_changed_files()
    if not changed_files:
        print("✅ No relevant code files changed. Skipping analysis.")
        sys.exit(0)

    payload_files = []
    for file_path in changed_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload_files.append({"path": file_path, "content": f.read()})
        except: pass

    payload = {
        "files": payload_files,
        "workspace": os.getenv("NEXUS_WORKSPACE", "default"),
        "project": os.getenv("NEXUS_PROJECT", "default"),
        "custom_rules": contract_rules 
    }

    try:
        response = requests.post(api_url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()

        print("\n📊 ANALYSIS RESULT: " + result.get('status', 'UNKNOWN'))
        
        details = result.get("details", [])
        
        # Post to GitHub PR
        if os.getenv("GITHUB_ACTIONS") == "true":
            post_github_comment(details)

        if result.get("status") == "FAIL":
            print("❌ Breach detected.")
            sys.exit(1)
        else:
            print("✅ Compliant.")
            sys.exit(0)

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        sys.exit(0)

if __name__ == "__main__":
    run_analysis()
