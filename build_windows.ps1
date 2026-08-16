$ErrorActionPreference = "Stop"
Write-Host "=== JARVIS OMEGA V6 - Windows EXE Build ===" -ForegroundColor Cyan

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Run setup_windows.ps1 first."
}

$python = Join-Path $PWD ".venv\Scripts\python.exe"
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed." }

Remove-Item -Recurse -Force ".\build" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ".\dist\JARVIS-OMEGA-V6" -ErrorAction SilentlyContinue

$hidden = @(
    "--hidden-import=edge_playback",
    "--hidden-import=speech_recognition",
    "--hidden-import=sounddevice",
    "--hidden-import=pyautogui",
    "--hidden-import=pypdf",
    "--hidden-import=docx",
    "--hidden-import=openpyxl"
)

$args = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onedir",
    "--windowed",
    "--name", "JARVIS-OMEGA-V6"
) + $hidden + @("desktop_app.py")

& $python @args
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$dist = Join-Path $PWD "dist\JARVIS-OMEGA-V6"
Copy-Item ".env.example" (Join-Path $dist ".env.example") -Force
Copy-Item "README.md" (Join-Path $dist "README.md") -Force
Copy-Item "LICENSE" (Join-Path $dist "LICENSE") -Force

Write-Host ""
Write-Host "Build complete: $dist" -ForegroundColor Green
Write-Host "IMPORTANT: API keys are NOT bundled." -ForegroundColor Yellow
Write-Host "Copy .env.example to .env inside the built folder and add your own provider key before running." -ForegroundColor Yellow
Write-Host "To make an installer, install Inno Setup and run .\build_installer.ps1" -ForegroundColor Cyan
