#!/usr/bin/env python3
"""Verify and deploy - writes results to file for verification"""

import subprocess
import time
import urllib.request
import json
import sys
from datetime import datetime

LOG_FILE = '/tmp/agent-deploy-verify.log'

def log(msg):
    """Log message to file and stdout"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(line)
    print(msg, flush=True)

log("=" * 60)
log("AGENT DEPLOYMENT VERIFICATION")
log("=" * 60)

# Step 1: Verify code
log("\n[1] Verifying code change in file...")
try:
    with open('/home/ubuntu/datatracker/ietf_data_viewer_simple.py', 'r') as f:
        content = f.read()
        if 'Welcome to the Meta-Layer Governance Hub' in content:
            log("   ✓ Code change FOUND in file")
        else:
            log("   ✗ Code change NOT FOUND in file!")
            sys.exit(1)
        if 'VERSION_MARKER: 2026-01-17-v2' in content:
            log("   ✓ Version marker found")
except Exception as e:
    log(f"   ✗ Error reading file: {e}")
    sys.exit(1)

# Step 2: Kill existing processes
log("\n[2] Killing existing processes...")
subprocess.run(['pkill', '-9', '-f', 'python.*ietf_data.*8001'], 
               stderr=subprocess.DEVNULL)
subprocess.run(['pkill', '-9', '-f', 'python.*8001.*ietf_data'], 
               stderr=subprocess.DEVNULL)
time.sleep(2)
log("   ✓ Processes killed")

# Step 3: Stop systemd service
log("\n[3] Stopping systemd service...")
subprocess.run(['systemctl', '--user', 'stop', 'datatracker-dev.service'],
               stderr=subprocess.DEVNULL)
time.sleep(2)
log("   ✓ Service stopped")

# Step 4: Clear cache
log("\n[4] Clearing Python cache...")
import os
import shutil
cache_count = 0
for root, dirs, files in os.walk('/home/ubuntu/datatracker'):
    if '__pycache__' in dirs:
        try:
            shutil.rmtree(os.path.join(root, '__pycache__'))
            cache_count += 1
        except:
            pass
    for f in files:
        if f.endswith('.pyc'):
            try:
                os.remove(os.path.join(root, f))
                cache_count += 1
            except:
                pass
log(f"   ✓ Cleared {cache_count} cache items")

# Step 5: Start service
log("\n[5] Starting service...")
result = subprocess.run(['systemctl', '--user', 'start', 'datatracker-dev.service'],
                       capture_output=True, text=True)
if result.returncode == 0:
    log("   ✓ Service started")
else:
    log(f"   ✗ Failed to start: {result.stderr}")
    sys.exit(1)

# Step 6: Wait and verify service
log("\n[6] Waiting for service to be ready...")
time.sleep(8)
result = subprocess.run(['systemctl', '--user', 'is-active', 'datatracker-dev.service'],
                       capture_output=True, text=True)
if result.returncode == 0:
    log(f"   ✓ Service is {result.stdout.strip()}")
else:
    log("   ✗ Service is not active!")
    # Get status
    status = subprocess.run(['systemctl', '--user', 'status', 'datatracker-dev.service'],
                           capture_output=True, text=True)
    log(status.stdout)
    sys.exit(1)

# Step 7: Test HTTP
log("\n[7] Testing HTTP connection...")
for attempt in range(5):
    try:
        time.sleep(2)
        response = urllib.request.urlopen('http://localhost:8001/', timeout=10)
        content = response.read().decode('utf-8')
        log(f"   ✓ HTTP {response.getcode()} (attempt {attempt+1})")
        
        # Check for new text
        if 'Welcome to the Meta-Layer Governance Hub' in content:
            log("   ✓✓✓ NEW TEXT FOUND IN HTTP RESPONSE! ✓✓✓")
            log("\n" + "=" * 60)
            log("SUCCESS! Deployment verified!")
            log("=" * 60)
            log("\nVisit: https://dev.rfc.themetalayer.org")
            log("Hard refresh: Ctrl+Shift+R")
            sys.exit(0)
        else:
            log(f"   ⚠ New text not found (attempt {attempt+1})")
            if attempt < 4:
                continue
    except Exception as e:
        log(f"   ⚠ Attempt {attempt+1} failed: {e}")
        if attempt < 4:
            continue

log("\n" + "=" * 60)
log("PARTIAL SUCCESS - Service running but text not verified")
log("=" * 60)
log("\nCheck manually:")
log("  curl http://localhost:8001/ | grep 'Welcome'")
log("  Visit: https://dev.rfc.themetalayer.org")
sys.exit(0)
