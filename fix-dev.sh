#!/bin/bash
# Fix development environment - complete restart

set -e

cd /home/ubuntu/datatracker

echo "=========================================="
echo "Fixing Development Environment"
echo "=========================================="

# Stop service
echo "1. Stopping development service..."
systemctl --user stop datatracker-dev.service || true
sleep 2

# Clear Python cache
echo "2. Clearing Python cache..."
find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Verify code change is in file
echo "3. Verifying code change..."
if grep -q "Welcome to the Meta-Layer Governance Hub" ietf_data_viewer_simple.py; then
    echo "   ✓ Code change found in file"
else
    echo "   ✗ Code change NOT found in file!"
    exit 1
fi

# Start service
echo "4. Starting development service..."
systemctl --user start datatracker-dev.service
sleep 5

# Verify it's running
echo "5. Verifying service status..."
if systemctl --user is-active --quiet datatracker-dev.service; then
    echo "   ✓ Service is running"
else
    echo "   ✗ Service failed to start"
    systemctl --user status datatracker-dev.service --no-pager | head -15
    exit 1
fi

# Check port
echo "6. Checking port 8001..."
sleep 2
if netstat -tlnp 2>/dev/null | grep -q ":8001 " || ss -tlnp 2>/dev/null | grep -q ":8001 "; then
    echo "   ✓ Port 8001 is listening"
else
    echo "   ✗ Port 8001 is NOT listening"
    exit 1
fi

# Test response
echo "7. Testing HTTP response..."
sleep 2
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ || echo "000")
if [ "$HTTP_CODE" == "200" ]; then
    echo "   ✓ Service responding (HTTP $HTTP_CODE)"
else
    echo "   ✗ Service not responding (HTTP $HTTP_CODE)"
    exit 1
fi

# Check for new text
echo "8. Checking for new text..."
if curl -s http://localhost:8001/ | grep -q "Welcome to the Meta-Layer Governance Hub"; then
    echo "   ✓ New text found!"
    echo ""
    echo "=========================================="
    echo "SUCCESS! Development environment is working"
    echo "Visit: https://dev.rfc.themetalayer.org"
    echo "=========================================="
else
    echo "   ⚠ New text not found in response"
    echo "   (Try hard refresh in browser: Ctrl+Shift+R)"
fi
