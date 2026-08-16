$ErrorActionPreference = "Stop"
Write-Host "=== JARVIS OMEGA V6 - Google Workspace Setup ===" -ForegroundColor Cyan

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Run .\setup_windows.ps1 first."
}

$python = Join-Path $PWD ".venv\Scripts\python.exe"
& $python -m pip install -r requirements-google.txt
if ($LASTEXITCODE -ne 0) { throw "Google Workspace dependency installation failed." }

Write-Host ""
Write-Host "Packages installed." -ForegroundColor Green
Write-Host "Next:" -ForegroundColor Cyan
Write-Host "1. In Google Cloud, enable Gmail API and Google Calendar API."
Write-Host "2. Create OAuth client: Desktop app."
Write-Host "3. Download the JSON and save it here as: google_credentials.json"
Write-Host "4. In .env set ENABLE_GOOGLE_WORKSPACE=true"
Write-Host "5. Restart JARVIS. The first Gmail/Calendar action will open a browser consent flow."
Write-Host ""
Write-Host "OAuth tokens are stored locally under data\google_token.json and are excluded from Git by data/." -ForegroundColor Yellow
