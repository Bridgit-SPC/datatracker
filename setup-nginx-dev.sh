#!/bin/bash
# Setup nginx reverse proxy for development server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Setting up Nginx for Development Server"
echo "=========================================="

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "This script needs sudo privileges to configure nginx"
    echo "Please run: sudo $0"
    exit 1
fi

# Copy nginx config
CONF_FILE="/etc/nginx/sites-available/dev.rfc.themetalayer.org"
cp "$SCRIPT_DIR/nginx-dev.conf" "$CONF_FILE"
echo "✓ Created nginx config: $CONF_FILE"

# Enable site
if [ ! -L "/etc/nginx/sites-enabled/dev.rfc.themetalayer.org" ]; then
    ln -s "$CONF_FILE" /etc/nginx/sites-enabled/dev.rfc.themetalayer.org
    echo "✓ Enabled nginx site"
else
    echo "✓ Site already enabled"
fi

# Test nginx configuration
echo "Testing nginx configuration..."
if nginx -t; then
    echo "✓ Nginx configuration is valid"
    systemctl reload nginx
    echo "✓ Nginx reloaded"
else
    echo "✗ Nginx configuration test failed!"
    exit 1
fi

echo ""
echo "=========================================="
echo "Nginx setup complete!"
echo ""
echo "Development server will be accessible at:"
echo "  http://dev.rfc.themetalayer.org"
echo ""
echo "Note: You'll need to add DNS A record for dev.rfc.themetalayer.org"
echo "pointing to: 216.238.91.120"
echo "=========================================="
