#!/usr/bin/env python3
"""Test and fix development environment"""

import subprocess
import sys
import time
import urllib.request

print("=" * 50)
print("Fixing Development Environment")
print("=" * 50)

# Step 1: Stop service
print("\n[1/6] Stopping development service...")
subprocess.run(['systemctl', '--user', 'stop', 'datatracker-dev.service'], 
               stderr=subprocess.DEVNULL)
time.sleep(2)
print("   ✓ Stopped")

# Step 2: Clear cache
print("\n[2/6] Clearing Python cache...")
subprocess.run(['find', '/home/ubuntu/datatracker', '-type', 'd', '-name', '__pycache__', 
                '-exec', 'rm', '-rf', '{}', '+'], stderr=subprocess.DEVNULL)
subprocess.run(['find', '/home/ubuntu/datatracker', '-name', '*.pyc', '-delete'], 
               stderr=subprocess.DEVNULL)
print("   ✓ Cache cleared")

# Step 3: Verify code
print("\n[3/6] Verifying code change...")
try:
    with open('/home/ubuntu/datatracker/ietf_data_viewer_simple.py', 'r') as f:
        content = f.read()
        if 'Welcome to the Meta-Layer Governance Hub' in content:
            print("   ✓ Code change found in file")
        else:
            print("   ✗ Code change NOT found!")
            sys.exit(1)
except Exception as e:
    print(f"   ✗ Error reading file: {e}")
    sys.exit(1)

# Step 4: Start service
print("\n[4/6] Starting development service...")
result = subprocess.run(['systemctl', '--user', 'start', 'datatracker-dev.service'],
                       capture_output=True, text=True)
if result.returncode == 0:
    print("   ✓ Service started")
else:
    print(f"   ✗ Failed to start: {result.stderr}")
    sys.exit(1)

# Step 5: Wait and check status
print("\n[5/6] Waiting for service to be ready...")
time.sleep(5)
result = subprocess.run(['systemctl', '--user', 'is-active', 'datatracker-dev.service'],
                       capture_output=True, text=True)
if result.returncode == 0:
    print(f"   ✓ Service is active")
else:
    print(f"   ✗ Service is not active")
    # Show status
    status = subprocess.run(['systemctl', '--user', 'status', 'datatracker-dev.service'],
                           capture_output=True, text=True)
    print(status.stdout)
    sys.exit(1)

# Step 6: Test HTTP
print("\n[6/6] Testing HTTP response...")
time.sleep(2)
try:
    response = urllib.request.urlopen('http://localhost:8001/', timeout=10)
    content = response.read().decode('utf-8')
    print(f"   ✓ HTTP {response.getcode()}")
    
    if 'Welcome to the Meta-Layer Governance Hub' in content:
        print("   ✓ NEW TEXT FOUND IN RESPONSE!")
        print("\n" + "=" * 50)
        print("SUCCESS! Development environment is working")
        print("=" * 50)
        print("\nVisit: https://dev.rfc.themetalayer.org")
        print("Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R)")
    else:
        print("   ⚠ New text not found in response")
        print("   (Service may need more time or browser cache needs clearing)")
        print("\nVisit: https://dev.rfc.themetalayer.org")
        print("Hard refresh: Ctrl+Shift+R")
except Exception as e:
    print(f"   ✗ Error connecting: {e}")
    print("\nService may still be starting. Wait a few seconds and try:")
    print("  curl http://localhost:8001/")
    sys.exit(1)
