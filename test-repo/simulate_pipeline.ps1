Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "[CI] Starting test phase on Nexus-X Worker" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Run Tests and pipe to txt file
$ErrorActionPreference = "SilentlyContinue"
C:\nexus-X\.venv\Scripts\python test_auth_raw.py | Out-File -FilePath pytest_output.txt
$ErrorActionPreference = "Continue"

Write-Host "Test phase finished. Analyzing result..."

# 2. Check if pytest failed by looking at string matching
$testOutput = Get-Content -Raw "pytest_output.txt"
if ($testOutput -match "FAILED") {
    Write-Host "[CI] Tests FAILED. Triggering Nexus-X Incident Orchestrator..." -ForegroundColor Red
    
    # 3. Capture Incident JSON
    Get-Content pytest_output.txt | C:\nexus-X\.venv\Scripts\python capture_incident.py
    
    # 4. Run Orchestrator
    Write-Host "[CI] Booting AI Forensic Agent..." -ForegroundColor Yellow
    $env:PYTHONPATH="C:\nexus-X\Orchestrator\src"
    $env:NEXUS_API_URL="http://127.0.0.1:8000"
    $env:NEXUS_LLM_PROVIDER="ollama"
    $env:NEXUS_LLM_MODEL="qwen2.5-coder:3b" # using the 3b model since the user might be on a laptop
    
    C:\nexus-X\.venv\Scripts\python -m orchestrator.main run incident.json --repo-root . --output-dir ci_reports
    
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host "[CI] Incident Investigation Complete. Report uploaded to CI artifacts." -ForegroundColor Green
} else {
    Write-Host "[CI] Tests PASSED. Proceeding to Deploy..." -ForegroundColor Green
}
