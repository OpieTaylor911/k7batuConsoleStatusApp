# Deployment Script for k7bat-uconsole-status
# ============================================
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/deploy-uconsole.ps1 [options]
#
# Options:
#   --UpdateOnly          Update only changed files (no full reinstall)
#   --SkipInstall         Skip running the installer
#   --SkipDiagnostics     Skip running diagnostics
#   --SkipSync            Skip file synchronization (update only)
#   -HostAlias <name>     Remote host alias (default: uconsole)
#   -RemoteDir <path>     Remote directory path (default: /opt/k7bat-uconsole-status)
#
# Examples:
#   # Full deployment (fresh install on target)
#   powershell -File scripts/deploy-uconsole.ps1
#
#   # Update only changed files (development mode)
#   powershell -File scripts/deploy-uconsole.ps1 -UpdateOnly
#
#   # Update without running diagnostics
#   powershell -File scripts/deploy-uconsole.ps1 -UpdateOnly -SkipDiagnostics

param(
    [string]$HostAlias = "uconsole",
    [string]$RemoteDir = "/opt/k7bat-uconsole-status",
    [switch]$SkipInstall,
    [switch]$SkipDiagnostics,
    [switch]$SkipSync,
    [switch]$UpdateOnly
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

# Normalize local shell scripts to Unix line endings before upload
Write-Host "==> Normalizing local shell script line endings"
Get-ChildItem -Path $projectRoot -Recurse -Include "*.sh", "k7bat-uconsole-status" | ForEach-Object {
    if (Select-String -Path $_.FullName -Pattern "`r`n" -Quiet) {
        (Get-Content $_.FullName -Raw) -replace "`r`n", "`n" | Set-Content $_.FullName -NoNewline
        Write-Host "   Fixed: $($_.Name)"
    }
}

if (-not $SkipSync) {
    if ($UpdateOnly) {
        Write-Host "==> Updating only changed files (no full reinstall)"
        
        # Upload only changed files to existing remote directory
        Write-Host "==> Uploading project files (incremental)"
        
        # Create remote directory if it doesn't exist
        Invoke-Remote "mkdir -p '$RemoteDir'"
        
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
        
        foreach ($src in $sources) {
            if (Test-Path $src) {
                Write-Host "   Uploading: $src"
                Invoke-Scp -Sources $src -Destination "${HostAlias}:$RemoteDir/"
            }
        }
        
        # Remove any duplicate app files that might exist outside the app directory
        Write-Host "==> Cleaning up stale app files on remote"
        $cleanupCmd = @(
            "cd '$RemoteDir'",
            "if [ -f 'k7bat-uconsole-status.py' ]; then",
            "    rm -f 'k7bat-uconsole-status.py'",
            "    echo 'Removed duplicate: k7bat-uconsole-status.py'",
            "fi"
        ) -join "`n"
        Invoke-Remote $cleanupCmd
        
        # Normalize line endings for updated shell scripts
        Write-Host "==> Normalizing remote shell script line endings"
        $normalizeCmd = @(
            "cd '$RemoteDir'",
            "if command -v dos2unix >/dev/null 2>&1; then",
            "    dos2unix install.sh uninstall.sh scripts/*.sh scripts/k7bat-uconsole-status 2>/dev/null || true",
            "else",
            "    find . -type f \( -name 'install.sh' -o -name 'uninstall.sh' -o -name '*.sh' -o -name 'k7bat-uconsole-status' \) -exec sed -i 's/\r$//' {} +",
            "fi"
        ) -join "`n"
        Invoke-Remote $normalizeCmd
    }
}

if (-not $UpdateOnly) {
    if (-not $SkipInstall) {
        Write-Host "==> Running installer on uConsole"
        $uidExpr = '$(id -u)'
            $installCmd = "cd '$RemoteDir' && chmod +x install.sh uninstall.sh scripts/*.sh scripts/k7bat-uconsole-status && if [ $uidExpr -eq 0 ]; then ./install.sh; else sudo ./install.sh; fi"
        Invoke-Remote $installCmd
    }
}

if (-not $SkipDiagnostics) {
    Write-Host "==> Running diagnostics on uConsole"
    Invoke-Remote "cd '$RemoteDir' && chmod +x scripts/diagnostics.sh && ./scripts/diagnostics.sh || true"
}

# Restart the application if it's running
Write-Host "==> Checking for running app process"
$checkProcCmd = "pgrep -f k7bat-uconsole-status || true"
$hasProcess = Invoke-Remote $checkProcCmd | Out-String
if ($hasProcess.Trim()) {
    Write-Host "==> Restarting k7bat-uconsole-status on uConsole"
    
    # Kill existing process (ignore errors if no process found)
    & ssh $HostAlias "pkill -f 'python3.*k7bat-uconsole-status' 2>/dev/null; true"
    
    Start-Sleep -Seconds 1
    
    # Start new process in background
    & ssh $HostAlias "cd '$RemoteDir'; nohup python3 app/k7bat-uconsole-status.py > /dev/null 2>&1 &"
}

Write-Host "==> Deploy workflow completed successfully"
