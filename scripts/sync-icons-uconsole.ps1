param(
    [string]$HostAlias = "uconsole",
    [string]$LocalIconDir = "assets/icons",
    [string]$RemoteIconDir = "/opt/k7bat-uconsole-status/icons"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path $LocalIconDir)) {
    throw "Icon directory not found: $LocalIconDir"
}

$icons = Get-ChildItem -Path $LocalIconDir -Filter *.svg -File
if (-not $icons -or $icons.Count -eq 0) {
    throw "No SVG icons found in $LocalIconDir"
}

Write-Host "==> Sync target: $HostAlias"
Write-Host "==> Local icons: $($icons.Count) file(s)"
Write-Host "==> Remote icon dir: $RemoteIconDir"

$remoteTmp = "/tmp/k7bat-icons"
& ssh $HostAlias "rm -rf '$remoteTmp' && mkdir -p '$remoteTmp'"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to prepare remote temp directory"
}

$sourceGlob = (Join-Path $LocalIconDir "*.svg")
& scp $sourceGlob "${HostAlias}:$remoteTmp/"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upload icon SVG files"
}

$installCmd = "sudo mkdir -p '$RemoteIconDir' && sudo cp '$remoteTmp'/*.svg '$RemoteIconDir'/"
& ssh $HostAlias $installCmd
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install icon files on remote"
}

Write-Host "==> Icon sync complete"
