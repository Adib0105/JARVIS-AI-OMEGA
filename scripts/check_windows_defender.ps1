param(
    [Parameter(Mandatory = $true)][string]$Target,
    [Parameter(Mandatory = $true)][string]$Report
)

# CI-only scan gate. Never restores threats or changes Defender preferences.
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$evidence = [ordered]@{
    result = 'failed'
    timestampUtc = [DateTime]::UtcNow.ToString('o')
    commit = $env:GITHUB_SHA
    target = $Target
    files = @()
}
try {
    $resolved = (Resolve-Path -LiteralPath $Target).Path
    $files = @(Get-ChildItem -LiteralPath $resolved -File -Recurse)
    if (Test-Path -LiteralPath $resolved -PathType Leaf) { $files = @(Get-Item -LiteralPath $resolved) }
    if ($files.Count -eq 0) { throw 'Scan target is empty.' }
    $manifest = @($files | ForEach-Object {
        [ordered]@{ path = $_.FullName; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
    })
    $evidence.files = $manifest
    $status = Get-MpComputerStatus -ErrorAction Stop
    if (-not $status.AMServiceEnabled -or -not $status.AntivirusEnabled) {
        throw 'Defender is unavailable or disabled. Release blocked; use a Windows runner with active Defender.'
    }
    Update-MpSignature -ErrorAction Stop
    $status = Get-MpComputerStatus -ErrorAction Stop
    $evidence.engineVersion = $status.AMEngineVersion
    $evidence.signatureVersion = $status.AntivirusSignatureVersion
    $evidence.signatureUpdated = $status.AntivirusSignatureLastUpdated
    if (-not $status.AntivirusSignatureLastUpdated -or $status.AntivirusSignatureLastUpdated -lt (Get-Date).AddDays(-2)) {
        throw 'Security intelligence is missing or stale.'
    }
    $platform = Join-Path $env:ProgramData 'Microsoft\Windows Defender\Platform'
    $scanner = Get-ChildItem -Path "$platform\*\MpCmdRun.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    if (-not $scanner) { $scanner = Join-Path $env:ProgramFiles 'Windows Defender\MpCmdRun.exe' }
    if (-not (Test-Path -LiteralPath $scanner)) { throw 'MpCmdRun scanner not found.' }
    # DisableRemediation applies only to this custom scan: it ignores exclusions,
    # scans archives and reports detections without treating removal as a pass.
    # Real-time protection remains unchanged.
    $output = & $scanner -Scan -ScanType 3 -File $resolved -DisableRemediation 2>&1
    $scanCode = $LASTEXITCODE
    $evidence.scanExitCode = $scanCode
    $evidence.scanOutput = ($output | Out-String)
    Write-Host $evidence.scanOutput
    if ($scanCode -ne 0) { throw "Defender scan failed or detected a threat (exit $scanCode)." }
    foreach ($entry in $manifest) {
        if (-not (Test-Path -LiteralPath $entry.path) -or (Get-FileHash -LiteralPath $entry.path -Algorithm SHA256).Hash -ne $entry.sha256) {
            throw 'A scanned file was removed or changed; release blocked.'
        }
    }
    $evidence.result = 'no_detection'
} catch {
    $evidence.error = $_.Exception.Message
    throw
} finally {
    $evidence | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Report -Encoding utf8
}
