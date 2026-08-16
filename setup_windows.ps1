$ErrorActionPreference = "Stop"
Write-Host "=== JARVIS AI OMEGA V6 - ARC Windows Setup ===" -ForegroundColor Cyan

$python = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $python = "py" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $python = "python" }
else { throw "Python 3.10+ not found. Install Python and enable Add Python to PATH." }

if (-not (Test-Path ".venv")) {
    Write-Host "Creating isolated V6 environment..." -ForegroundColor Cyan
    & $python -m venv .venv
}

$venvPython = Join-Path $PWD ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }

Write-Host "Installing JARVIS V6 core packages..." -ForegroundColor Cyan
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Core dependency installation failed." }

if (Test-Path "requirements-windows.txt") {
    Write-Host "Installing optional Windows desktop automation + microphone packages..." -ForegroundColor Cyan
    & $venvPython -m pip install -r requirements-windows.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Optional Windows packages could not all be installed. Text chat still works; MIC/desktop automation may be unavailable."
    }
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example" -ForegroundColor Green
} else {
    Write-Host "Existing .env kept unchanged. V6-only options use safe defaults from config.py." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "1. Keep your provider/API key in .env" -ForegroundColor White
Write-Host "2. Run self-check: .\.venv\Scripts\python.exe self_check.py"
Write-Host "3. Desktop ARC V6: .\run_desktop.bat"
Write-Host "4. Terminal V6: .\run_jarvis.bat"
Write-Host ""
Write-Host "V6 modules: animated ARC HUD, typed + spoken replies, optional MIC/wake word, image/screen vision, documents, memory, tasks/reminders, browser/app controls, guarded desktop automation, coding workspace tools, missions, and live system telemetry." -ForegroundColor Cyan
Write-Host "Sensitive local actions remain permission-gated." -ForegroundColor Yellow
