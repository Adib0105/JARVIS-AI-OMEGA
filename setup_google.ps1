$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host '=== JARVIS AI OMEGA // Google Workspace Setup ===' -ForegroundColor Cyan

$python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'JARVIS environment not found. Run .\setup_windows.ps1 first.'
}

$Version = (& $python -c "from jarvis.version import APP_VERSION; print(APP_VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $Version) { throw 'Could not read canonical application version.' }
Write-Host "JARVIS AI OMEGA $Version" -ForegroundColor Cyan

Write-Host 'Installing pinned Google Workspace dependencies through release constraints...' -ForegroundColor Cyan
& $python -m pip install -c constraints-release.txt -r requirements-google.txt
if ($LASTEXITCODE -ne 0) { throw 'Google Workspace dependency installation failed.' }

& $python -c "import googleapiclient, google_auth_httplib2, google_auth_oauthlib"
if ($LASTEXITCODE -ne 0) { throw 'Google Workspace dependency import verification failed.' }

Write-Host ''
Write-Host 'Google Workspace software dependencies installed and importable.' -ForegroundColor Green
Write-Host 'Next:' -ForegroundColor Cyan
Write-Host '1. In Google Cloud, enable Gmail API and Google Calendar API.'
Write-Host '2. Create an OAuth client of type Desktop app.'
Write-Host '3. Download the OAuth client JSON and save it locally as google_credentials.json.'
Write-Host '4. In .env set ENABLE_GOOGLE_WORKSPACE=true.'
Write-Host '5. Restart JARVIS. The first Gmail/Calendar action will open the Google consent flow.'
Write-Host ''
Write-Host 'OAuth credentials/tokens are local secrets and must never be committed or bundled into a release.' -ForegroundColor Yellow
Write-Host 'Package installation is not OAuth/live Gmail/Calendar verification; record that evidence separately.' -ForegroundColor Yellow
