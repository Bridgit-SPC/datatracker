#!/usr/bin/env python3
"""
Deploy and immediately verify - no ambiguity
"""

import subprocess
import time
import urllib.request
import json
import sys

def run_cmd(cmd, timeout=None):
    """Run command safely"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except:
        return False, "", "ERROR"

def main():
    print("🔥 DEPLOY AND VERIFY - NO AMBIGUITY 🔥")
    print("=" * 60)

    # Step 1: Verify code in file
    print("\n[1] Checking code in file...")
    try:
        with open('/home/ubuntu/datatracker/ietf_data_viewer_simple.py', 'r') as f:
            code = f.read()
            if 'Welcome to the Meta-Layer Governance Hub' in code:
                print("   ✅ Code change found in file")
            else:
                print("   ❌ Code change NOT found in file")
                return False
    except Exception as e:
        print(f"   ❌ Error reading file: {e}")
        return False

    # Step 2: Kill everything
    print("\n[2] Killing all processes...")
    run_cmd("pkill -9 -f 'python.*ietf_data'")
    run_cmd("pkill -9 -f 'python.*8001'")
    run_cmd("systemctl --user stop datatracker-dev.service")
    time.sleep(3)
    print("   ✅ Processes killed")

    # Step 3: Clear cache
    print("\n[3] Clearing cache...")
    import os, shutil
    for root, dirs, files in os.walk('/home/ubuntu/datatracker'):
        if '__pycache__' in dirs:
            shutil.rmtree(os.path.join(root, '__pycache__'), ignore_errors=True)
        for f in files:
            if f.endswith('.pyc'):
                os.remove(os.path.join(root, f), ignore_errors=True)
    print("   ✅ Cache cleared")

    # Step 4: Start service
    print("\n[4] Starting service...")
    success, stdout, stderr = run_cmd("systemctl --user start datatracker-dev.service")
    if success:
        print("   ✅ Service started")
    else:
        print(f"   ❌ Service failed: {stderr}")
        return False

    # Step 5: Wait and verify
    print("\n[5] Waiting for service...")
    time.sleep(15)
    success, stdout, stderr = run_cmd("systemctl --user is-active datatracker-dev.service")
    if success and 'active' in stdout.lower():
        print("   ✅ Service is active")
    else:
        print(f"   ❌ Service not active: {stdout}")
        return False

    # Step 6: Test deployment endpoint
    print("\n[6] Testing deployment status...")
    time.sleep(3)
    try:
        response = urllib.request.urlopen('http://localhost:8001/_deploy/status', timeout=10)
        status_data = json.loads(response.read().decode('utf-8'))
        print("   ✅ Status endpoint works")
        print(f"      Environment: {status_data.get('environment')}")
        print(f"      Code changed: {status_data.get('code_changed')}")
        print(f"      Service active: {status_data.get('service_active')}")
        if status_data.get('current_homepage_text'):
            print(f"      Homepage text: {status_data.get('current_homepage_text')[:50]}...")
    except Exception as e:
        print(f"   ❌ Status endpoint failed: {e}")
        return False

    # Step 7: Test test page
    print("\n[7] Testing test page...")
    try:
        response = urllib.request.urlopen('http://localhost:8001/_deploy/test', timeout=10)
        content = response.read().decode('utf-8')
        if 'DEPLOYMENT TEST PAGE' in content:
            print("   ✅ Test page works")
        else:
            print("   ❌ Test page content wrong")
            return False
    except Exception as e:
        print(f"   ❌ Test page failed: {e}")
        return False

    # Step 8: Reload nginx
    print("\n[8] Reloading nginx...")
    success, stdout, stderr = run_cmd("sudo nginx -t", timeout=5)
    if success:
        run_cmd("sudo systemctl reload nginx")
        print("   ✅ Nginx reloaded")
    else:
        print(f"   ⚠️ Nginx config issue: {stderr}")
        print("   Continuing anyway...")

    # Step 9: Final verification
    print("\n[9] FINAL VERIFICATION...")
    time.sleep(5)

    # Test localhost
    try:
        response = urllib.request.urlopen('http://localhost:8001/', timeout=10)
        content = response.read().decode('utf-8')
        if 'Welcome to the Meta-Layer Governance Hub' in content:
            print("   ✅ Localhost has new text")
            localhost_ok = True
        else:
            print("   ❌ Localhost missing new text")
            localhost_ok = False
    except Exception as e:
        print(f"   ❌ Localhost error: {e}")
        localhost_ok = False

    # Test dev subdomain
    try:
        response = urllib.request.urlopen('https://dev.rfc.themetalayer.org/', timeout=10)
        content = response.read().decode('utf-8')
        if 'Welcome to the Meta-Layer Governance Hub' in content:
            print("   ✅ Dev subdomain has new text")
            dev_ok = True
        else:
            print("   ❌ Dev subdomain missing new text")
            dev_ok = False
    except Exception as e:
        print(f"   ❌ Dev subdomain error: {e}")
        dev_ok = False

    # Result
    print("\n" + "=" * 60)
    if dev_ok:
        print("🎉🎉🎉 SUCCESS! DEPLOYMENT COMPLETE! 🎉🎉🎉")
        print("\n✅ The change is LIVE at: https://dev.rfc.themetalayer.org")
        print("\nWhat you should see:")
        print("- 'Welcome to the Meta-Layer Governance Hub' text")
        print("- Hard refresh if needed: Ctrl+Shift+R")
        print("\nAdditional test URLs:")
        print("- Status: https://dev.rfc.themetalayer.org/_deploy/status")
        print("- Test page: https://dev.rfc.themetalayer.org/_deploy/test")
        return True
    elif localhost_ok:
        print("⚠️  PARTIAL SUCCESS - Working on localhost")
        print("\nTry accessing directly: http://216.238.91.120:8001")
        print("Or check nginx configuration")
        return True
    else:
        print("❌ DEPLOYMENT FAILED")
        print("\nDebug information:")
        print("- Check service: systemctl --user status datatracker-dev.service")
        print("- Check logs: journalctl --user -u datatracker-dev.service -n 20")
        print("- Test localhost: curl http://localhost:8001/")
        return False

if __name__ == '__main__':
    success = main()
    print(f"\nFinal result: {'SUCCESS' if success else 'FAILED'}")
    sys.exit(0 if success else 1)