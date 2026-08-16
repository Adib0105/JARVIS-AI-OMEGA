$ErrorActionPreference = "Stop"
Write-Host "=== JARVIS OMEGA V3 - Windows Setup ===" -ForegroundColor Cyan

$python = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $python = "py" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $python = "python" }
else { throw "Python 3.10+ not found. Install Python and enable Add Python to PATH." }

if (-not (Test-Path ".venv")) {
    & $python -m venv .venv
}

$venvPython = Join-Path $PWD ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example" -ForegroundColor Green
} else {
    Write-Host "Existing .env kept unchanged." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Free test mode:" -ForegroundColor Cyan
Write-Host "1. Open .env"
Write-Host "2. Set AI_PROVIDER=openrouter"
Write-Host "3. Set OPENROUTER_API_KEY=your_key"
Write-Host "4. Keep OPENROUTER_MODEL=openrouter/free"
Write-Host "5. Run: .\.venv\Scripts\python.exe self_check.py"
Write-Host "6. Terminal JARVIS: .\.venv\Scripts\python.exe main.py"
Write-Host "7. Desktop OMEGA UI: .\.venv\Scripts\python.exe desktop_app.py"
Write-Host ""
Write-Host "OMEGA V3 includes free public web search, local knowledge indexing, chat export, and deeper neural voice." -ForegroundColor Cyan
