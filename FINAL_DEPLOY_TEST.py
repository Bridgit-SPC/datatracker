#!/usr/bin/env python3
"""Final deployment test - writes all output to file"""

import subprocess
import time
import json
import urllib.request
import sys
from datetime import datetime

OUTPUT_FILE = '/home/ubuntu/datatracker/DEPLOY_RESULT.txt'

def write_result(msg):
    with open(OUTPUT_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()}: {msg}\n")
    print(msg, flush=True)

write_result("=" * 60)
write_result("FINAL DEPLOYMENT TEST")
write_result("=" * 60)

# Step 1: Verify code
write_result("\n[1] Reading code file...")
try:
    with open('/home/ubuntu/datatracker/ietf_data_viewer_simple.py', 'r') as f:
        code_content = f.read()
        write_result(f"   File size: {len(code_content)} bytes")
        
        if 'Welcome to the Meta-Layer Governance Hub' in code_content:
            write_result("   ✓ NEW TEXT FOUND IN FILE")
        else:
            write_result("   ✗ NEW TEXT NOT IN FILE!")
            sys.exit(1)
            
        # Extract the actual text
        import re
        match = re.search(r'<p class="lead">(.*?)</p>', code_content)
        if match:
            write_result(f"   Found text in code: {match.group(1)}")
except Exception as e:
    write_result(f"   ✗ Error: {e}")
    sys.exit(1)

# Step 2: Kill and restart
write_result("\n[2] Restarting service...")
subprocess.run(['pkill', '-9', '-f', '8001'], stderr=subprocess.DEVNULL)
subprocess.run(['systemctl', '--user', 'stop', 'datatracker-dev.service'], stderr=subprocess.DEVNULL)
time.sleep(3)

# Clear cache
import os
import shutil
for root, dirs, files in os.walk('/home/ubuntu/datatracker'):
    if '__pycache__' in dirs:
        try:
            shutil.rmtree(os.path.join(root, '__pycache__'))
        except:
            pass

subprocess.run(['systemctl', '--user', 'start', 'datatracker-dev.service'])
time.sleep(10)

# Step 3: Test
write_result("\n[3] Testing endpoints...")
for i in range(3):
    try:
        time.sleep(3)
        # Test status endpoint
        response = urllib.request.urlopen('http://localhost:8001/_test/homepage-text', timeout=10)
        data = json.loads(response.read().decode('utf-8'))
        write_result(f"\n   Test endpoint response:")
        write_result(f"   {json.dumps(data, indent=2)}")
        
        # Test homepage
        response = urllib.request.urlopen('http://localhost:8001/', timeout=10)
        content = response.read().decode('utf-8')
        write_result(f"\n   Homepage HTTP: {response.getcode()}")
        write_result(f"   Homepage length: {len(content)} bytes")
        
        if 'Welcome to the Meta-Layer Governance Hub' in content:
            write_result("   ✓✓✓ NEW TEXT FOUND IN HOMEPAGE! ✓✓✓")
            write_result("\n" + "=" * 60)
            write_result("SUCCESS!")
            write_result("=" * 60)
            sys.exit(0)
        else:
            # Find what text is actually there
            import re
            match = re.search(r'<p class="lead">(.*?)</p>', content)
            if match:
                write_result(f"   Found text in homepage: {match.group(1)}")
            else:
                write_result("   No <p class='lead'> found in homepage")
                
    except Exception as e:
        write_result(f"   Attempt {i+1} failed: {e}")
        if i < 2:
            continue

write_result("\n" + "=" * 60)
write_result("TEST COMPLETE - Check DEPLOY_RESULT.txt for details")
write_result("=" * 60)
