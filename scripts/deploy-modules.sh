#!/bin/bash
# Deploy built modules to web server
# This script symlinks built modules to lighttpd's document root

set -e

echo "=== Deploying Pineapple Modules to Web Server ==="
echo ""

MODULES_DIR="/home/bcaddy/.config/k7bat-uconsole-status/pineapple-modules"
WEB_ROOT="/var/www/html/modules"

# Check if modules directory exists
if [ ! -d "$MODULES_DIR" ]; then
    echo "ERROR: Modules directory not found at $MODULES_DIR"
    exit 1
fi

# Start lighttpd if not running
echo "Checking web server..."
if ! pgrep -x "lighttpd" > /dev/null; then
    echo "Starting lighttpd..."
    sudo service lighttpd start || sudo systemctl start lighttpd
else
    echo "lighttpd is already running"
fi

# Create web root directory
echo ""
echo "Setting up web root..."
sudo mkdir -p "$WEB_ROOT"
sudo rm -rf "${WEB_ROOT:?}"/*

# Create symlinks for each module's dist folder
echo ""
echo "Creating symlinks..."

for module_dir in "$MODULES_DIR"/*/; do
    if [ -d "$module_dir" ]; then
        module_name=$(basename "$module_dir")
        dist_path="${module_dir}dist/${module_name}"
        
        if [ -d "$dist_path" ]; then
            echo "  Linking $module_name -> $dist_path"
            sudo ln -sf "$dist_path" "${WEB_ROOT}/${module_name}"
        else
            echo "  WARNING: $module_name not built (no dist folder)"
        fi
    fi
done

# Set proper ownership
echo ""
echo "Setting permissions..."
sudo chown -R www-data:www-data "$WEB_ROOT"

# Fix permission chain for www-data to access modules via symlinks
echo ""
echo "Fixing home directory permissions..."
sudo chmod o+rx /home/bcaddy/
sudo chmod o+x /home/bcaddy/.config/

# Generate index.html for each module (Angular libraries need a wrapper)
echo ""
echo "Generating index.html files..."
for module_dir in "$MODULES_DIR"/*/; do
    if [ -d "$module_dir" ]; then
        module_name=$(basename "$module_dir")
        link_path="${WEB_ROOT}/${module_name}"
        
        if [ -L "$link_path" ]; then
            # Get actual target of symlink (already points to dist folder)
            target=$(readlink -f "$link_path")
            
            # The target already is the dist folder, so index.html should be there
            index_file="${target}/index.html"
            if [ ! -f "$index_file" ]; then
                cat > "$index_file" << HTMLEOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${module_name^}</title>
    <base href=".">
    <style>
        body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        .loading { display: flex; justify-content: center; align-items: center; height: 100vh; }
    </style>
</head>
<body>
    <div id="app" class="loading">
        <h2>Loading ${module_name}...</h2>
    </div>
    <script src="bundles/runtime.js"></script>
    <script src="bundles/polyfills.js"></script>
    <script src="bundles/main.js"></script>
</body>
</html>
HTMLEOF
                echo "  Created index.html for $module_name"
            fi
        fi
    fi
done

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Modules are now accessible at:"
echo "  http://localhost/modules/{module_name}"
echo ""
echo "Available modules:"
ls -la "$WEB_ROOT" | grep "^l" | awk '{print "  - " $NF}'
echo ""
