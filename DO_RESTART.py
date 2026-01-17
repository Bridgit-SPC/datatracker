#!/usr/bin/env python3
import subprocess
import time
import urllib.request
import sys

print("Killing processes...")
subprocess.run(['pkill', '-9', '-f', '8001'], stderr=subprocess.DEVNULL)
subprocess.run(['systemctl', '--user', 'stop', 'datatracker-dev.service'], stderr=subprocess.DEVNULL)
time.sleep(3)

print("Clearing cache...")
import os, shutil
for root, dirs, files in os.walk('/home/ubuntu/datatracker'):
    if '__pycache__' in dirs:
        shutil.rmtree(os.path.join(root, '__pycache__'), ignore_errors=True)
    for f in files:
        if f.endswith('.pyc'):
            os.remove(os.path.join(root, f), ignore_errors=True)

print("Starting service...")
subprocess.run(['systemctl', '--user', 'start', 'datatracker-dev.service'])
time.sleep(10)

print("Testing...")
try:
    response = urllib.request.urlopen('http://localhost:8001/', timeout=10)
    content = response.read().decode('utf-8')
    with open('/tmp/homepage-content.html', 'w') as f:
        f.write(content)
    if 'Welcome to the Meta-Layer Governance Hub' in content:
        print("SUCCESS: New text found!")
        sys.exit(0)
    else:
        print("FAILED: New text not found")
        print("Content saved to /tmp/homepage-content.html")
        sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
