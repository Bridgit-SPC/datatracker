#!/usr/bin/env python3
"""
Agent deployment script - Python version for reliable execution
"""
import subprocess
import sys
import time
import urllib.request
import json

def agent_deploy(env='development'):
    """Deploy to specified environment"""
    print(f"=== AGENT DEPLOYMENT: {env.upper()} ===")
    print()
    
    # Run the bash script
    try:
        result = subprocess.run(
            ['bash', 'agent-deploy.sh', env],
            capture_output=True,
            text=True,
            timeout=60,
            cwd='/home/ubuntu/datatracker'
        )
        
        print("DEPLOYMENT OUTPUT:")
        print(result.stdout)
        if result.stderr:
            print("ERRORS:")
            print(result.stderr)
        print()
        
        # Parse output
        if "AGENT_RESULT|SUCCESS" in result.stdout:
            print("✓ DEPLOYMENT SUCCESSFUL")
            
            # Verify via API
            print("\nVerifying via API...")
            time.sleep(2)
            try:
                port = 8001 if env == 'development' else 8000
                response = urllib.request.urlopen(f'http://localhost:{port}/_deploy/status', timeout=5)
                status = json.loads(response.read().decode('utf-8'))
                print(f"Environment: {status['environment']}")
                print(f"Service active: {status['service_active']}")
                print(f"Has new text: {status['has_new_text']}")
                
                # Test content
                response = urllib.request.urlopen(f'http://localhost:{port}/', timeout=5)
                content = response.read().decode('utf-8')
                if 'Welcome to the Meta-Layer Governance Hub' in content:
                    print("✓ New text verified in HTTP response")
                else:
                    print("⚠ New text not found (may need browser refresh)")
                    
            except Exception as e:
                print(f"⚠ API verification failed: {e}")
            
            return True
        elif "AGENT_RESULT|ERROR" in result.stdout:
            print("✗ DEPLOYMENT FAILED")
            return False
        else:
            print("⚠ DEPLOYMENT STATUS UNKNOWN")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ DEPLOYMENT TIMED OUT")
        return False
    except Exception as e:
        print(f"✗ DEPLOYMENT ERROR: {e}")
        return False

if __name__ == '__main__':
    env = sys.argv[1] if len(sys.argv) > 1 else 'development'
    success = agent_deploy(env)
    sys.exit(0 if success else 1)
