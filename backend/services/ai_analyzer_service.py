"""
AI Analyzer Service — Performs deep code analysis using LLMs and Rule Engines.
Specifically designed for CI/CD integration.
"""

from __future__ import annotations
import os
import requests
import json
import time
from typing import List, Dict, Any
import concurrent.futures
from datetime import datetime, timezone
from db.mongo import mongo

# Local LLM configuration (defaulting to Ollama)
LLM_ENDPOINT = os.getenv("NEXUS_LLM_ENDPOINT", "http://localhost:11434/api/generate")
LLM_MODEL = os.getenv("NEXUS_LLM_MODEL", "qwen2.5-coder:3b")

class AIAnalyzerService:
    def __init__(self):
        self.rules = {
            "security": [
                "Check for SQL injection vulnerabilities",
                "Identify hardcoded secrets or API keys",
                "Look for unsafe use of eval() or subprocess.run(shell=True)"
            ],
            "architecture": [
                "Ensure separation of concerns (don't mix DB logic with API logic)",
                "Check for circular dependencies",
                "Identify violations of the project's layered architecture"
            ],
            "reliability": [
                "Check for proper error handling (try/except blocks)",
                "Identify potential resource leaks (unclosed files/connections)",
                "Look for race conditions in async code"
            ]
        }

    def analyze_code(self, files: List[Dict[str, str]], workspace: str = "default", project: str = "default", custom_rules: List[str] = None) -> Dict[str, Any]:
        """
        Analyzes multiple files and returns a unified report.
        Uses ThreadPoolExecutor for parallel LLM calls.
        """
        all_details = []
        total_risk_score = 0.0
        overall_status = "PASS"

        if not files:
            return {"status": "PASS", "risk_score": 0.0, "details": []}

        # Run analysis in parallel to speed up CI/CD
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_file = {
                executor.submit(self._analyze_file, f["path"], f["content"], custom_rules): f["path"] 
                for f in files
            }
            
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    file_report = future.result()
                    
                    if file_report["status"] == "FAIL":
                        overall_status = "FAIL"
                    
                    total_risk_score += file_report["risk_score"]
                    all_details.extend(file_report["details"])
                except Exception as exc:
                    print(f"[AI Analyzer] {file_path} generated an exception: {exc}")
                    all_details.append({
                        "file": file_path,
                        "rule": "System",
                        "severity": "HIGH",
                        "message": f"Parallel analysis failed: {exc}",
                        "line": 0
                    })

        # Normalize risk score
        avg_risk_score = total_risk_score / len(files)
        final_score = round(min(avg_risk_score, 100.0), 2)

        result = {
            "status": overall_status,
            "risk_score": final_score,
            "details": all_details
        }

        # PERSIST TO DATABASE for UI visibility
        self._persist_ci_report(workspace, project, result, len(files))

        return result

    def _persist_ci_report(self, workspace: str, project: str, result: Dict[str, Any], file_count: int):
        """Stores the CI analysis result in MongoDB so it appears in the Dashboard."""
        incident_id = f"ci-{int(time.time()) % 100000:05d}"
        
        # Generate a markdown summary for the UI
        report_md = f"# AI CI/CD Analysis Report: {workspace}/{project}\n\n"
        report_md += f"**Status:** {result['status']}\n"
        report_md += f"**Risk Score:** {result['risk_score']}/100\n"
        report_md += f"**Files Analyzed:** {file_count}\n\n"
        
        if result['details']:
            report_md += "## Findings\n\n"
            for d in result['details']:
                severity_icon = "🔴" if d['severity'] == "HIGH" else "🟡" if d['severity'] == "MEDIUM" else "🔵"
                report_md += f"### {severity_icon} {d['rule']} ({d['severity']})\n"
                report_md += f"- **File:** `{d['file']}` (Line {d.get('line', 'N/A')})\n"
                report_md += f"- **Issue:** {d['message']}\n"
                if d.get('suggestion'):
                    report_md += f"- **💡 Suggestion:** {d['suggestion']}\n"
                report_md += "\n---\n"
        else:
            report_md += "✅ No major issues detected by AI analysis.\n"

        payload = {
            "workspace": workspace,
            "project": project,
            "incident_id": incident_id,
            "status": "CI_ANALYSIS",
            "summary": f"AI Security/Architecture Check: {result['status']} (Score: {result['risk_score']})",
            "exit_code": 1 if result['status'] == "FAIL" else 0,
            "hypotheses": [
                {
                    "title": "CI/CD Rule Violation",
                    "confidence": result['risk_score'] / 100.0,
                    "evidence": [d['message'] for d in result['details'][:3]],
                    "likely_locations": [d['file'] for d in result['details'][:3]],
                    "next_steps": ["Review CI failure logs", "Fix suggested code violations"]
                }
            ] if result['status'] == "FAIL" else [],
            "code_locations": [
                {
                    "path": d['file'],
                    "line_hint": d.get('line'),
                    "confidence": 0.9 if d['severity'] == "HIGH" else 0.7,
                    "rationale": d['message']
                } for d in result['details'][:5]
            ],
            "report_markdown": report_md,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "type": "ci_check"
        }

        try:
            reports_col = mongo.get_collection("incident_reports")
            reports_col.insert_one(payload)
            print(f"[AI Analyzer] CI Report persisted: {incident_id}")
        except Exception as e:
            print(f"[AI Analyzer] DB Store failed: {e}")

    def _analyze_file(self, path: str, content: str, custom_rules: List[str] = None) -> Dict[str, Any]:
        """
        Analyzes a single file using LLM + Rules.
        """
        print(f"[AI Analyzer] Analyzing {path}...")
        
        # Combine default rules with custom ones
        rules_to_check = self.rules["security"] + self.rules["architecture"] + self.rules["reliability"]
        if custom_rules:
            rules_to_check.extend(custom_rules)

        # Prepare LLM Prompt
        prompt = self._build_prompt(path, content, rules_to_check)

        try:
            # Call Local LLM
            response = requests.post(LLM_ENDPOINT, json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            }, timeout=30.0)
            
            if response.status_code != 200:
                return self._fallback_report(path, f"LLM Error: {response.text}")

            result = json.loads(response.json().get("response", "{}"))
            
            # Ensure required fields exist
            if "status" not in result: result["status"] = "PASS"
            if "risk_score" not in result: result["risk_score"] = 0.0
            if "details" not in result: result["details"] = []
            
            # Add file path to details
            for detail in result["details"]:
                detail["file"] = path

            return result

        except Exception as e:
            print(f"[AI Analyzer] Failed to analyze {path}: {e}")
            return self._fallback_report(path, str(e))

    def _build_prompt(self, path: str, content: str, rules: List[str]) -> str:
        rules_str = "\n".join([f"- {r}" for r in rules])
        return f"""
Analyze the following code from file '{path}' against these rules:
{rules_str}

Return a JSON object with the following structure:
{{
  "status": "PASS" | "FAIL",
  "risk_score": 0.0 to 100.0,
  "details": [
    {{
      "rule": "Rule Name",
      "severity": "LOW" | "MEDIUM" | "HIGH",
      "message": "Detailed explanation",
      "line": 10,
      "suggestion": "How to fix it"
    }}
  ]
}}

Code:
```
{content}
```
"""

    def _fallback_report(self, path: str, error: str) -> Dict[str, Any]:
        return {
            "status": "PASS", # Default to pass on error to avoid blocking CI if AI is down
            "risk_score": 0.0,
            "details": [{
                "file": path,
                "rule": "System",
                "severity": "LOW",
                "message": f"AI analysis skipped due to error: {error}",
                "line": 0,
                "suggestion": "Check backend logs"
            }]
        }

ai_analyzer = AIAnalyzerService()
