#!/bin/bash
# Setup SSL certificate for development server

set -e

echo "=========================================="
echo "Setting up SSL for Development Server"
echo "=========================================="

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "This script needs sudo privileges"
    echo "Please run: sudo $0"
    exit 1
fi

# Check if nginx config exists
if [ ! -f "/etc/nginx/sites-enabled/dev.rfc.themetalayer.org" ]; then
    echo "Error: Nginx config not found. Run setup-nginx-dev.sh first."
    exit 1
fi

# Get email from user or use default
EMAIL="${1:-daveed@bridgit.io}"
echo "Using email: $EMAIL"

# Run certbot
echo "Requesting SSL certificate from Let's Encrypt..."
certbot --nginx -d dev.rfc.themetalayer.org \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    --redirect

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "SSL certificate installed successfully!"
    echo ""
    echo "Development server is now available at:"
    echo "  https://dev.rfc.themetalayer.org"
    echo ""
    echo "HTTP will automatically redirect to HTTPS"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "SSL certificate installation failed!"
    echo ""
    echo "Common issues:"
    echo "1. DNS not propagated - wait a few minutes"
    echo "2. Port 80 not accessible - check firewall"
    echo "3. Domain already has certificate - check /etc/letsencrypt/live/"
    echo "=========================================="
    exit 1
fi
