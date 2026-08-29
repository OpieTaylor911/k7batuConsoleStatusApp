#!/usr/bin/env powershell
# Update k7bat-uconsole-status on uConsole without full reinstall
# Usage: .\scripts\update-uconsole.ps1 [-SkipDiagnostics]

param(
    [switch]$SkipDiagnostics
)

Write-Host "==> Updating k7bat-uconsole-status on uConsole"
Write-Host ""

# Normalize local shell scripts to Unix line endings before upload
Write-Host "==> Normalizing local shell script line endings..."
Get-ChildItem -Path "scripts" -Recurse -Include "*.sh", "k7bat-uconsole-status" | ForEach-Object {
    if (Select-String -Path $_.FullName -Pattern "`r`n" -Quiet) {
        (Get-Content $_.FullName -Raw) -replace "`r`n", "`n" | Set-Content $_.FullName -NoNewline
        Write-Host "   Fixed: $($_.Name)"
    }
}

# Upload files to existing remote directory
Write-Host "==> Uploading changed files..."
$remoteDir = "/home/bcaddy/uconsole-k7bat/app"
& ssh uconsole "mkdir -p '$remoteDir'"

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
        Write-Host "   Uploading: $src..."
        & scp -r $src uconsole:"$remoteDir/" 2>&1 | Out-Null
    }
}

# Normalize line endings on remote side
Write-Host "==> Normalizing remote shell script line endings..."
$normalizeCmd = @(
    "cd '$remoteDir'",
    "if command -v dos2unix >/dev/null 2>&1; then",
    "    dos2unix install.sh uninstall.sh scripts/*.sh scripts/k7bat-uconsole-status 2>/dev/null || true",
    "else",
    "    find . -type f \( -name 'install.sh' -o -name 'uninstall.sh' -o -name '*.sh' -o -name 'k7bat-uconsole-status' \) -exec sed -i 's/\r$//' {} +",
    "fi"
) -join "`n"
ssh uconsole $normalizeCmd

Write-Host ""
Write-Host "==> Update completed successfully!"
Write-Host ""

if (-not $SkipDiagnostics) {
    Write-Host "==> Running diagnostics..."
    ssh uconsole "cd '$remoteDir' && chmod +x scripts/diagnostics.sh && ./scripts/diagnostics.sh || true"
}

Write-Host ""
Write-Host "Useful commands:"
Write-Host "  cd $remoteDir && python3 app/k7bat-uconsole-status.py"
Write-Host "  ssh uconsole 'cd $remoteDir && ./install.sh'    # Full reinstall if needed"
