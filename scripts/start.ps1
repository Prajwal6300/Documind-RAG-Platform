# Windows PowerShell Startup Script for DocuMind Platform
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Starting DocuMind Enterprise RAG Platform" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Start FastAPI Backend in background job
Write-Host "`n[1/2] Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    Set-Location -Path $using:PWD
    & ".\venv\Scripts\python" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
}
Start-Sleep -Seconds 3

# 2. Start Vite Frontend
Write-Host "[2/2] Starting Vite Frontend on http://localhost:5173..." -ForegroundColor Yellow
Set-Location -Path "frontend"
npm run dev
