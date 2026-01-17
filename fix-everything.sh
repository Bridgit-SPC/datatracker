#!/bin/bash
# Complete fix for development deployment

echo "=== COMPLETE FIX FOR DEVELOPMENT ==="

# 1. Kill all processes
echo "1. Killing all processes..."
pkill -9 -f "python.*ietf_data" 2>&1
pkill -9 -f "python.*8001" 2>&1
systemctl --user stop datatracker-dev.service 2>&1
sleep 3

# 2. Clear all cache
echo "2. Clearing cache..."
cd /home/ubuntu/datatracker
find . -type d -name __pycache__ -exec rm -rf {} + 2>&1
find . -name "*.pyc" -delete 2>&1

# 3. Verify code
echo "3. Verifying code..."
if grep -q "Welcome to the Meta-Layer Governance Hub" ietf_data_viewer_simple.py; then
    echo "   ✓ Code verified"
else
    echo "   ✗ Code not found!"
    exit 1
fi

# 4. Start service
echo "4. Starting dev service..."
systemctl --user start datatracker-dev.service
sleep 8

# 5. Check service
echo "5. Checking service..."
if systemctl --user is-active --quiet datatracker-dev.service; then
    echo "   ✓ Service active"
else
    echo "   ✗ Service not active"
    systemctl --user status datatracker-dev.service --no-pager | head -10
    exit 1
fi

# 6. Test localhost
echo "6. Testing localhost..."
sleep 2
HTTP_LOCAL=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ 2>&1)
echo "   Localhost HTTP: $HTTP_LOCAL"

# 7. Reload nginx
echo "7. Reloading nginx..."
sudo nginx -t 2>&1
if [ $? -eq 0 ]; then
    sudo systemctl reload nginx 2>&1
    echo "   ✓ Nginx reloaded"
else
    echo "   ✗ Nginx config error"
    exit 1
fi

# 8. Test dev subdomain
echo "8. Testing dev subdomain..."
sleep 3
HTTP_DEV=$(curl -s -o /dev/null -w "%{http_code}" https://dev.rfc.themetalayer.org/ 2>&1)
echo "   Dev HTTP: $HTTP_DEV"

# 9. Check for new text
echo "9. Checking for new text..."
TEXT_DEV=$(curl -s https://dev.rfc.themetalayer.org/ 2>&1 | grep -o "Welcome to the Meta-Layer Governance Hub" | head -1)
if [ "$TEXT_DEV" == "Welcome to the Meta-Layer Governance Hub" ]; then
    echo "   ✓✓✓ SUCCESS! New text found! ✓✓✓"
    echo ""
    echo "=========================================="
    echo "DEPLOYMENT COMPLETE!"
    echo "Visit: https://dev.rfc.themetalayer.org"
    echo "=========================================="
    exit 0
else
    echo "   ✗ New text not found"
    echo "   Checking what we got..."
    curl -s https://dev.rfc.themetalayer.org/ 2>&1 | head -100 | python3 -c "
import sys
import re
content = sys.stdin.read()
print('Response length:', len(content))
match = re.search(r'<p class=\"lead\">(.*?)</p>', content)
if match:
    print('Found lead text:', match.group(1))
else:
    print('No <p class=\"lead\"> found')
    print('First 300 chars:')
    print(content[:300])
"
    exit 1
fi
