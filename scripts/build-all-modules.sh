#!/bin/bash
# Build all Pineapple modules script
# This script installs Node.js if needed and builds all modules

set -e

echo "=== Building All Pineapple Modules ==="
echo ""

MODULES_DIR="/home/bcaddy/.config/k7bat-uconsole-status/pineapple-modules"

# Check if modules directory exists
if [ ! -d "$MODULES_DIR" ]; then
    echo "ERROR: Modules directory not found at $MODULES_DIR"
    exit 1
fi

# Install Node.js if not available
echo "Checking for Node.js..."
if ! command -v node &> /dev/null; then
    echo "Node.js not found. Installing..."
    
    # Update package list
    sudo apt-get update
    
    # Install curl if needed
    if ! command -v curl &> /dev/null; then
        sudo apt-get install -y curl
    fi
    
    # Install Node.js using NodeSource (supports Debian 13)
    echo "Installing Node.js via NodeSource..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
    
    echo "Node.js installed successfully"
else
    echo "Node.js already installed"
fi

# Verify installation
echo ""
echo "Node version: $(node --version)"
echo "NPM version: $(npm --version)"

# Build each module
echo ""
echo "=== Building Modules ==="

for module_dir in "$MODULES_DIR"/*/; do
    if [ -d "$module_dir" ]; then
        module_name=$(basename "$module_dir")
        echo ""
        echo "--- Building $module_name ---"
        
        cd "$module_dir"
        
        # Check if package.json exists
        if [ ! -f "package.json" ]; then
            echo "WARNING: No package.json found in $module_name, skipping..."
            continue
        fi
        
        # Install dependencies if node_modules doesn't exist
        if [ ! -d "node_modules" ]; then
            echo "Installing dependencies for $module_name..."
            npm install --production=false 2>&1 | tail -5 || echo "Dependencies may already be installed"
        fi
        
        # Build the module (non-interactive)
        if [ -f "build.sh" ]; then
            echo "Running build script for $module_name..."
            
            # Run build.sh with forced workspace setup (skip interactive prompts)
            # by setting up node_modules first, then running build directly
            if [ ! -d "node_modules" ] || [ ! -f "angular.json" ]; then
                echo "[*] Preparing Angular workspace (non-interactive)..."
                npm install --silent 2>&1 | tail -3 || true
            fi
            
            # Run the actual build (bypass interactive check)
            echo "[*] Building $module_name..."
            if NODE_OPTIONS="--no-deprecation" npx ng build --prod 2>&1; then
                echo "[*] Angular Build Succeeded"
                
                # Copy required files to build output (same as build.sh does)
                MODULENAME="$module_name"
                cp -r projects/$MODULENAME/src/module.svg dist/$MODULENAME/bundles/ 2>/dev/null || true
                cp -r projects/$MODULENAME/src/module.json dist/$MODULENAME/bundles/ 2>/dev/null || true
                cp -r projects/$MODULENAME/src/module.py dist/$MODULENAME/bundles/ 2>/dev/null || true
                
                # Clean up maps and min files
                rm -rf dist/$MODULENAME/bundles/*.map 2>/dev/null || true
                rm -rf dist/$MODULENAME/bundles/*.min* 2>/dev/null || true
                
                echo "[*] $module_name built successfully"
            else
                echo "[!] Angular Build Failed for $module_name"
            fi
        elif [ -f "package.json" ]; then
            # Try to build using ng build directly
            echo "Building $module_name with ng build..."
            npx ng build --prod 2>&1 || echo "Build failed for $module_name"
        else
            echo "WARNING: No build script found in $module_name, skipping..."
        fi
        
        echo "--- Finished $module_name ---"
    fi
done

echo ""
echo "=== Build Complete ==="
echo ""
echo "To deploy modules to web server:"
echo "  sudo service lighttpd start"
echo "  sudo mkdir -p /var/www/html/modules"
echo "  cd /var/www/html/modules && sudo rm -rf *"
echo "  for dir in $MODULES_DIR/*/; do sudo ln -sf \"\$dir\" \"/var/www/html/modules/\$(basename \"\$dir\")\"; done"
echo ""
echo "Modules will be accessible at: http://localhost/modules/{module_name}"
echo ""
