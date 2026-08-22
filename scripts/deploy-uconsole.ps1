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

    Write-Host "==> Normalizing remote shell script line endings"
        $normalizeCmd = @"
cd '$RemoteDir'
if command -v dos2unix >/dev/null 2>&1; then
    dos2unix install.sh uninstall.sh scripts/*.sh scripts/k7bat-uconsole-status >/dev/null 2>&1 || true
else
    sed -i 's/\r$//' install.sh uninstall.sh scripts/*.sh scripts/k7bat-uconsole-status
fi
"@
        Invoke-Remote $normalizeCmd
}

if (-not $SkipInstall) {
    Write-Host "==> Running installer on uConsole"
    $uidExpr = '$(id -u)'
        $installCmd = "cd '$RemoteDir' && chmod +x install.sh uninstall.sh scripts/*.sh scripts/k7bat-uconsole-status && if [ $uidExpr -eq 0 ]; then ./install.sh; else sudo ./install.sh; fi"
    Invoke-Remote $installCmd
}

if (-not $SkipDiagnostics) {
    Write-Host "==> Running diagnostics on uConsole"
    Invoke-Remote "cd '$RemoteDir' && chmod +x scripts/diagnostics.sh && ./scripts/diagnostics.sh || true"
}

Write-Host "==> Deploy workflow completed successfully"
