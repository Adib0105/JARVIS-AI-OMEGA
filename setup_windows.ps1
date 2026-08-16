$ErrorActionPreference = "Stop"
Write-Host "=== JARVIS OMEGA - Windows Setup ===" -ForegroundColor Cyan

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
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "1. Open .env and set OPENAI_API_KEY"
Write-Host "2. Run: .\.venv\Scripts\python.exe self_check.py"
Write-Host "3. Start: .\.venv\Scripts\python.exe main.py"
