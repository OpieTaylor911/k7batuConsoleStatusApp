param(
    [string]$HostAlias = "uconsole",
    [string]$RemoteDir = "/tmp/k7bat-uconsole-status-src",
    [switch]$SkipInstall,
    [switch]$SkipDiagnostics,
    [switch]$SkipSync
)

$ErrorActionPreference = "Stop"

function Invoke-Remote {
    param(
        [Parameter(Mandatory = $true)][string]$Command
    )
    & ssh $HostAlias $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Remote command failed: $Command"
    }
}

function Invoke-Scp {
    param(
        [Parameter(Mandatory = $true)][string[]]$Sources,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    & scp -r @Sources $Destination
    if ($LASTEXITCODE -ne 0) {
        throw "SCP transfer failed to $Destination"
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "==> Deploy target: $HostAlias"
Write-Host "==> Local project: $projectRoot"
Write-Host "==> Remote directory: $RemoteDir"

if (-not $SkipSync) {
    Write-Host "==> Preparing remote directory"
    Invoke-Remote "rm -rf '$RemoteDir' && mkdir -p '$RemoteDir'"

    $sources = @(
        "app",
        "assets",
        "scripts",
        "install.sh",
        "uninstall.sh",
        "README.md",
        "CHANGELOG.md",
        "FORUM_POST.md",
        "LICENSE",
        "VERSION",
        "SHA256SUMS"
    )

    Write-Host "==> Uploading project files"
    Invoke-Scp -Sources $sources -Destination "${HostAlias}:$RemoteDir/"
}

if (-not $SkipInstall) {
    Write-Host "==> Running installer on uConsole"
    $uidExpr = '$(id -u)'
    $installCmd = "cd '$RemoteDir' && chmod +x install.sh uninstall.sh scripts/*.sh && if [ $uidExpr -eq 0 ]; then ./install.sh; else sudo ./install.sh; fi"
    Invoke-Remote $installCmd
}

if (-not $SkipDiagnostics) {
    Write-Host "==> Running diagnostics on uConsole"
    Invoke-Remote "cd '$RemoteDir' && chmod +x scripts/diagnostics.sh && ./scripts/diagnostics.sh"
}

Write-Host "==> Deploy workflow completed successfully"
