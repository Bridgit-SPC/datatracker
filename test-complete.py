#!/usr/bin/env python3
"""
Complete test of the deployment system
"""

import subprocess
import time
import urllib.request
import sys

def run_cmd(cmd):
    """Run command and return success, stdout, stderr"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0, result.stdout.strip(), result.stderr.strip()

def write_result(msg):
    """Write result to file and print"""
    with open('/tmp/test-results.txt', 'a') as f:
        f.write(msg + '\n')
    print(msg)

def main():
    write_result("=" * 60)
    write_result("COMPLETE DEPLOYMENT TEST")
    write_result("=" * 60)

    # 1. Check if code has new text
    write_result("\n1. Checking code...")
    try:
        with open('/home/ubuntu/datatracker/ietf_data_viewer_simple.py', 'r') as f:
            code = f.read()
            if 'Welcome to the Meta-Layer Governance Hub' in code:
                write_result("   ✓ Code has new text")
            else:
                write_result("   ✗ Code missing new text!")
                return False
    except Exception as e:
        write_result(f"   ✗ Error reading code: {e}")
        return False

    # 2. Kill and restart service
    write_result("\n2. Restarting service...")
    run_cmd("pkill -9 -f 'python.*ietf_data'")
    run_cmd("pkill -9 -f 'python.*8001'")
    run_cmd("systemctl --user stop datatracker-dev.service")
    time.sleep(3)

    # Clear cache
    import os, shutil
    for root, dirs, files in os.walk('/home/ubuntu/datatracker'):
        if '__pycache__' in dirs:
            shutil.rmtree(os.path.join(root, '__pycache__'), ignore_errors=True)
        for f in files:
            if f.endswith('.pyc'):
                os.remove(os.path.join(root, f), ignore_errors=True)

    success, stdout, stderr = run_cmd("systemctl --user start datatracker-dev.service")
    if success:
        write_result("   ✓ Service started")
    else:
        write_result(f"   ✗ Service failed: {stderr}")
        return False
    time.sleep(10)

    # 3. Check service status
    write_result("\n3. Checking service status...")
    success, stdout, stderr = run_cmd("systemctl --user is-active datatracker-dev.service")
    if success and 'active' in stdout.lower():
        write_result("   ✓ Service is active")
    else:
        write_result(f"   ✗ Service not active: {stdout}")
        return False

    # 4. Reload nginx
    write_result("\n4. Reloading nginx...")
    success, stdout, stderr = run_cmd("sudo nginx -t")
    if success:
        run_cmd("sudo systemctl reload nginx")
        write_result("   ✓ Nginx reloaded")
    else:
        write_result(f"   ✗ Nginx config error: {stderr}")
        return False
    time.sleep(3)

    # 5. Test localhost
    write_result("\n5. Testing localhost...")
    time.sleep(2)
    try:
        response = urllib.request.urlopen('http://localhost:8001/', timeout=10)
        content_local = response.read().decode('utf-8')
        write_result(f"   ✓ Localhost HTTP {response.getcode()}")
    except Exception as e:
        write_result(f"   ✗ Localhost error: {e}")
        content_local = ""

    # 6. Test dev subdomain
    write_result("\n6. Testing dev subdomain...")
    time.sleep(2)
    try:
        response = urllib.request.urlopen('https://dev.rfc.themetalayer.org/', timeout=10)
        content_dev = response.read().decode('utf-8')
        write_result(f"   ✓ Dev subdomain HTTP {response.getcode()}")
    except Exception as e:
        write_result(f"   ✗ Dev subdomain error: {e}")
        content_dev = ""

    # 7. Check for new text
    write_result("\n7. Checking for new text...")

    text_found = False
    if 'Welcome to the Meta-Layer Governance Hub' in content_local:
        write_result("   ✓ New text found on LOCALHOST!")
        text_found = True
    else:
        write_result("   ✗ New text NOT found on localhost")

    if 'Welcome to the Meta-Layer Governance Hub' in content_dev:
        write_result("   ✓✓✓ New text found on DEV SUBDOMAIN! ✓✓✓")
        text_found = True
    else:
        write_result("   ✗ New text NOT found on dev subdomain")

    # 8. Results
    write_result("\n" + "=" * 60)
    if text_found:
        write_result("SUCCESS! The change is live.")
        write_result("Visit: https://dev.rfc.themetalayer.org")
        write_result("Hard refresh: Ctrl+Shift+R")
        return True
    else:
        write_result("FAILED! Text not found anywhere.")
        write_result("\nDebug info:")
        if content_dev:
            import re
            match = re.search(r'<p class="lead">(.*?)</p>', content_dev)
            if match:
                write_result(f"Dev subdomain text: '{match.group(1)}'")
            else:
                write_result("No <p class='lead'> found on dev subdomain")
        return False
    write_result("=" * 60)

if __name__ == '__main__':
    # Clear previous results
    open('/tmp/test-results.txt', 'w').close()
    success = main()
    write_result(f"\nFinal result: {'SUCCESS' if success else 'FAILED'}")

    # Save content for inspection
    try:
        response = urllib.request.urlopen('https://dev.rfc.themetalayer.org/', timeout=5)
        content = response.read().decode('utf-8')
        with open('/tmp/dev-content.html', 'w') as f:
            f.write(content)
        write_result("Dev content saved to /tmp/dev-content.html")
    except:
        pass

    sys.exit(0 if success else 1)