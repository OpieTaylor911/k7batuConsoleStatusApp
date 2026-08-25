#!/usr/bin/env pwsh
# Deploy Hak5 Pineapple modules plugin to uConsole

Write-Host "Deploying Hak5 Pineapple Modules Plugin..."

# Configuration
$UConsoleHost = "uconsole"
$PluginSourceDir = "./app/plugins"
$RemoteBasePath = "/opt/k7bat-uconsole-status"

# Create remote plugin directory
Write-Host "Creating remote plugin directory..."
ssh $UConsoleHost "mkdir -p $RemoteBasePath/plugins"

# Copy plugin files
Write-Host "Copying plugin files..."
scp "$PluginSourceDir/__init__.py" "${UConsoleHost}:${RemoteBasePath}/plugins/"
scp "$PluginSourceDir/pineapple_loader.py" "${UConsoleHost}:${RemoteBasePath}/plugins/"
scp "$PluginSourceDir/pineapple_ui.py" "${UConsoleHost}:${RemoteBasePath}/plugins/"

# Create modules directory on uConsole
Write-Host "Creating modules directory..."
ssh $UConsoleHost "mkdir -p ~/.config/k7bat-uconsole-status/pineapple_modules"

Write-Host "Deployment complete!"
Write-Host ""
Write-Host "To install Hak5 Pineapple modules:"
Write-Host "1. Open the Status App"
Write-Host "2. Click 'Hak5 Pineapple' button in the plugin row"
Write-Host "3. Click 'Install Module' and enter repository URL"
Write-Host "   Example: https://github.com/hak5/pineapple-modules.git"
Write-Host ""
Write-Host "Available Hak5 modules with Python backend:"
ssh $UConsoleHost "git clone --depth 1 https://github.com/hak5/pineapple-modules.git /tmp/pineapple-modules 2>/dev/null || true"
ssh $UConsoleHost "find /tmp/pineapple-modules -name 'module.py' -type f | head -20 | xargs -I{} dirname {} | sed 's|/tmp/pineapple-modules/||'"
