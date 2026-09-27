# Exercise the real updater checkpoint functions under Windows PowerShell 5.1.
# Parse only these trusted local function definitions; never run an installer.
$ErrorActionPreference = 'Stop'
$Tokens = $null
$Errors = $null
$Ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'apply-update.ps1'), [ref]$Tokens, [ref]$Errors)
if ($Errors.Count) { throw 'Updater syntax is invalid.' }
foreach ($Name in @('Copy-Owned', 'Get-OwnedManifest', 'Assert-Manifest')) {
    $Function = $Ast.Find({ param($Node) $Node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $Node.Name -eq $Name }, $true)
    if (-not $Function) { throw ('Missing checkpoint function: ' + $Name) }
    . ([ScriptBlock]::Create($Function.Extent.Text))
}
$Owned = @('JARVIS-OMEGA-V7.exe', '_internal', 'apply-update.ps1')
$Root = Join-Path $env:TEMP ('jarvis-checkpoint-test-' + [guid]::NewGuid().ToString('N'))
$Source = Join-Path $Root 'original'
$Backup = Join-Path $Root 'backup'
try {
    New-Item -ItemType Directory -Path (Join-Path $Source '_internal\nested'), $Backup -Force | Out-Null
    'exe sample' | Set-Content (Join-Path $Source $Owned[0])
    'library sample' | Set-Content (Join-Path $Source '_internal\nested\module.bin')
    'helper sample' | Set-Content (Join-Path $Source $Owned[2])
    $Manifest = @(Get-OwnedManifest $Source)
    Copy-Owned $Source $Backup
    Assert-Manifest $Backup $Manifest
    $Json = ConvertTo-Json -InputObject $Manifest -Depth 3
    $Reloaded = $Json | ConvertFrom-Json
    Assert-Manifest $Backup $Reloaded
    # Compatibility with both enumeration behaviors; comparison is per file,
    # not a JSON serialization/property-order comparison.
    $Nested = @($Json | ConvertFrom-Json)
    Assert-Manifest $Backup $Nested
    Add-Content (Join-Path $Backup '_internal\nested\module.bin') 'corruption'
    $Rejected = $false
    try { Assert-Manifest $Backup $Reloaded } catch { $Rejected = $true }
    if (-not $Rejected) { throw 'Corrupt library checkpoint was accepted.' }
    Write-Host 'Checkpoint copy / persisted JSON / corrupt library rejection PASS.'
} finally {
    Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue
}
