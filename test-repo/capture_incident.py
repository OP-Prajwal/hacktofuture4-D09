import sys
import json
import uuid
import datetime

def main():
    log_content = sys.stdin.read()
    
    # We want to grab the main Error message and stack trace.
    # Pytest output contains them in "FAILURES" block.
    
    error_summary = "Test Suite Failure"
    stack_trace = ""
    
    if "FAILED" in log_content:
        lines = log_content.split("\n")
        err_lines = [l for l in lines if l.startswith("E   ")]
        if err_lines:
            error_summary = err_lines[0].replace("E   ", "").strip()
            
        stack_start = log_content.find("Traceback (most recent call last):")
        if stack_start != -1:
            stack_trace = log_content[stack_start:].replace("=============================", "").strip()
    
    incident = {
      "id": f"inc-{uuid.uuid4().hex[:6]}",
      "title": "CI/CD Deployment Failure in Test Suite",
      "service": "test-repo",
      "environment": "ci-pipeline",
      "error_summary": error_summary,
      "stack_trace": stack_trace,
      "logs": log_content.split("\n")[-20:] # Last 20 lines of pytest
    }
    
    with open("incident.json", "w") as f:
        json.dump(incident, f, indent=2)
        
    print(f"Captured CI crash into incident.json with error: {error_summary}")

if __name__ == "__main__":
    main()
