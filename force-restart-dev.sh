#!/bin/bash
# Force restart development service - kills process and restarts

set -e

echo "=== FORCE RESTART DEVELOPMENT ==="

# Kill any existing process on port 8001
echo "1. Killing existing processes..."
pkill -9 -f "python.*ietf_data.*8001" 2>/dev/null || true
pkill -9 -f "python.*8001.*ietf_data" 2>/dev/null || true
sleep 2

# Stop systemd service
echo "2. Stopping systemd service..."
systemctl --user stop datatracker-dev.service 2>/dev/null || true
sleep 2

# Clear all cache
echo "3. Clearing cache..."
cd /home/ubuntu/datatracker
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Verify code
echo "4. Verifying code..."
if grep -q "Welcome to the Meta-Layer Governance Hub" ietf_data_viewer_simple.py; then
    echo "   ✓ Code verified"
else
    echo "   ✗ Code NOT found!"
    exit 1
fi

# Start service
echo "5. Starting service..."
systemctl --user start datatracker-dev.service
sleep 8

# Verify
echo "6. Verifying..."
if systemctl --user is-active --quiet datatracker-dev.service; then
    echo "   ✓ Service active"
else
    echo "   ✗ Service not active"
    systemctl --user status datatracker-dev.service --no-pager | head -20
    exit 1
fi

# Test HTTP
echo "7. Testing HTTP..."
sleep 3
for i in {1..5}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ --max-time 5 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" == "200" ]; then
        echo "   ✓ HTTP 200"
        
        # Check content
        CONTENT=$(curl -s http://localhost:8001/ --max-time 5 2>/dev/null || echo "")
        if echo "$CONTENT" | grep -q "Welcome to the Meta-Layer Governance Hub"; then
            echo "   ✓ NEW TEXT FOUND!"
            echo ""
            echo "=== SUCCESS ==="
            echo "Visit: https://dev.rfc.themetalayer.org"
            exit 0
        else
            echo "   ⚠ Text not found (attempt $i)"
            if [ $i -lt 5 ]; then
                sleep 2
            fi
        fi
    else
        echo "   ⚠ HTTP $HTTP_CODE (attempt $i)"
        if [ $i -lt 5 ]; then
            sleep 2
        fi
    fi
done

echo ""
echo "=== PARTIAL SUCCESS ==="
echo "Service is running. Try browser refresh."
exit 0
