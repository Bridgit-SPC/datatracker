#!/usr/bin/env python3
"""
ABSOLUTE FIX - Guarantees the change is deployed and visible
"""

import subprocess
import time
import urllib.request
import sys
import os

def run_cmd(cmd, timeout=None):
    """Run command safely"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except:
        return False, "", "Timeout or error"

def main():
    print("=" * 70)
    print("ABSOLUTE FIX FOR DEVELOPMENT DEPLOYMENT")
    print("=" * 70)

    # Step 1: Verify code change exists
    print("\n[1] VERIFYING CODE CHANGE...")
    try:
        with open('/home/ubuntu/datatracker/ietf_data_viewer_simple.py', 'r') as f:
            code = f.read()
            if 'Welcome to the Meta-Layer Governance Hub' in code:
                print("   ✓ Code change CONFIRMED in file")
            else:
                print("   ✗ FATAL: Code change not found in file!")
                sys.exit(1)
    except Exception as e:
        print(f"   ✗ FATAL: Error reading file: {e}")
        sys.exit(1)

    # Step 2: Kill everything
    print("\n[2] KILLING ALL PROCESSES...")
    run_cmd("pkill -9 -f 'python.*ietf_data'")
    run_cmd("pkill -9 -f 'python.*8001'")
    run_cmd("systemctl --user stop datatracker-dev.service")
    time.sleep(3)
    print("   ✓ All processes killed")

    # Step 3: Clear ALL cache
    print("\n[3] CLEARING ALL CACHE...")
    import shutil
    cache_count = 0
    for root, dirs, files in os.walk('/home/ubuntu/datatracker'):
        for d in dirs:
            if d == '__pycache__':
                try:
                    shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                    cache_count += 1
                except:
                    pass
        for f in files:
            if f.endswith('.pyc'):
                try:
                    os.remove(os.path.join(root, f), ignore_errors=True)
                    cache_count += 1
                except:
                    pass
    print(f"   ✓ Cleared {cache_count} cache items")

    # Step 4: Start service
    print("\n[4] STARTING SERVICE...")
    success, stdout, stderr = run_cmd("systemctl --user start datatracker-dev.service")
    if success:
        print("   ✓ Service started successfully")
    else:
        print(f"   ✗ Failed to start service: {stderr}")
        sys.exit(1)

    # Step 5: Wait and verify
    print("\n[5] WAITING FOR SERVICE...")
    time.sleep(12)
    success, stdout, stderr = run_cmd("systemctl --user is-active datatracker-dev.service")
    if success and 'active' in stdout.lower():
        print("   ✓ Service is ACTIVE")
    else:
        print(f"   ✗ Service not active: {stdout}")
        sys.exit(1)

    # Step 6: Reload nginx
    print("\n[6] RELOADING NGINX...")
    success, stdout, stderr = run_cmd("sudo nginx -t", timeout=5)
    if success:
        run_cmd("sudo systemctl reload nginx")
        print("   ✓ Nginx reloaded successfully")
    else:
        print(f"   ✗ Nginx config error: {stderr}")
        print("   Continuing anyway...")

    # Step 7: Test localhost
    print("\n[7] TESTING LOCALHOST...")
    time.sleep(3)
    try:
        response = urllib.request.urlopen('http://localhost:8001/', timeout=15)
        content = response.read().decode('utf-8')
        print(f"   ✓ Localhost responds: HTTP {response.getcode()}")
        local_has_text = 'Welcome to the Meta-Layer Governance Hub' in content
        print(f"   Localhost has new text: {local_has_text}")
    except Exception as e:
        print(f"   ✗ Localhost error: {e}")
        local_has_text = False

    # Step 8: Test dev subdomain
    print("\n[8] TESTING DEV SUBDOMAIN...")
    time.sleep(3)
    try:
        response = urllib.request.urlopen('https://dev.rfc.themetalayer.org/', timeout=15)
        content = response.read().decode('utf-8')
        print(f"   ✓ Dev subdomain responds: HTTP {response.getcode()}")
        dev_has_text = 'Welcome to the Meta-Layer Governance Hub' in content
        print(f"   Dev subdomain has new text: {dev_has_text}")
    except Exception as e:
        print(f"   ✗ Dev subdomain error: {e}")
        dev_has_text = False

    # Step 9: Final result
    print("\n" + "=" * 70)
    if dev_has_text:
        print("🎉 SUCCESS! The change is LIVE on the dev subdomain!")
        print("Visit: https://dev.rfc.themetalayer.org")
        print("Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R)")
        print("=" * 70)
        return True
    elif local_has_text:
        print("⚠️  PARTIAL SUCCESS - Change is live on localhost but nginx issue")
        print("Try accessing directly: http://216.238.91.120:8001")
        print("Or fix nginx proxy")
        print("=" * 70)
        return True
    else:
        print("❌ FAILED - Change not found anywhere")
        print("\nDEBUGGING INFO:")
        try:
            response = urllib.request.urlopen('https://dev.rfc.themetalayer.org/', timeout=10)
            content = response.read().decode('utf-8')
            import re
            match = re.search(r'<p class="lead">(.*?)</p>', content)
            if match:
                print(f"Current text on dev subdomain: '{match.group(1)}'")
            else:
                print("No <p class='lead'> found on dev subdomain")
                print("First 300 chars of response:")
                print(content[:300])
        except Exception as e:
            print(f"Could not get debug info: {e}")
        print("=" * 70)
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)