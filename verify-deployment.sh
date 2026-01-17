#!/bin/bash
# Verify deployment is working

ENV="${1:-development}"
PORT="${2:-8001}"

if [ "$ENV" == "production" ]; then
    PORT=8000
    URL="https://rfc.themetalayer.org"
else
    PORT=8001
    URL="https://dev.rfc.themetalayer.org"
fi

echo "=========================================="
echo "Verifying $ENV deployment"
echo "=========================================="

# Check if service is running
if [ "$ENV" == "production" ]; then
    if systemctl --user is-active --quiet datatracker.service; then
        echo "✓ Production service is running"
    else
        echo "✗ Production service is NOT running"
        exit 1
    fi
else
    if systemctl --user is-active --quiet datatracker-dev.service; then
        echo "✓ Development service is running"
    else
        echo "✗ Development service is NOT running"
        exit 1
    fi
fi

# Check if port is listening
if netstat -tlnp 2>/dev/null | grep -q ":$PORT " || ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
    echo "✓ Port $PORT is listening"
else
    echo "✗ Port $PORT is NOT listening"
    exit 1
fi

# Check if we can connect
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/" | grep -q "200"; then
    echo "✓ Service responding on port $PORT"
else
    echo "✗ Service NOT responding on port $PORT"
    exit 1
fi

# Check for the new text (if we know what to look for)
if curl -s "http://localhost:$PORT/" | grep -q "Welcome to the Meta-Layer Governance Hub"; then
    echo "✓ New text found in response"
else
    echo "⚠ New text not found (may need browser refresh)"
fi

echo ""
echo "=========================================="
echo "Verification complete"
echo "Access at: $URL"
echo "=========================================="
