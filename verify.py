#!/usr/bin/env python3
"""
Verification Script - Verify deployment after changes

Usage:
    python3 verify.py dev          # Verify development
    python3 verify.py prod         # Verify production
"""

import os
import sys
import subprocess
import json
import requests
from datetime import datetime
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent.absolute()

ENV_CONFIG = {
    'dev': {
        'url': 'https://dev.rfc.themetalayer.org',
        'port': 8001
    },
    'prod': {
        'url': 'https://rfc.themetalayer.org',
        'port': 8000
    }
}

# Expected content checks
EXPECTED_CONTENT = {
    'homepage': {
        'text': 'Welcome to the Meta-Layer Governance Hub',
        'should_contain': True
    },
    'title': {
        'text': 'MLTF',
        'should_contain': True
    }
}

def log(message, level='INFO'):
    """Log message"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [{level}] {message}")

def check_http_response(url, expected_status=200):
    """Check HTTP response"""
    try:
        response = requests.get(url, timeout=10, verify=False)
        return {
            'success': response.status_code == expected_status,
            'status_code': response.status_code,
            'content': response.text,
            'response_time': response.elapsed.total_seconds()
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def check_content(content, checks):
    """Check if content contains expected text"""
    results = {}
    for check_name, check_config in checks.items():
        text = check_config['text']
        should_contain = check_config.get('should_contain', True)
        contains = text in content
        
        if should_contain:
            results[check_name] = {
                'expected': f"Should contain: {text}",
                'found': contains,
                'success': contains
            }
        else:
            results[check_name] = {
                'expected': f"Should NOT contain: {text}",
                'found': contains,
                'success': not contains
            }
    
    return results

def check_api_endpoints(base_url):
    """Check API endpoints"""
    endpoints = [
        '/',
        '/doc/draft/',
        '/documents',
        '/_deploy/status'
    ]
    
    results = {}
    for endpoint in endpoints:
        url = base_url.rstrip('/') + endpoint
        result = check_http_response(url)
        results[endpoint] = result
    
    return results

def verify_environment(env):
    """Verify environment"""
    if env not in ENV_CONFIG:
        log(f"Invalid environment: {env}", 'ERROR')
        return False
    
    config = ENV_CONFIG[env]
    base_url = config['url']
    
    log(f"Verifying {env} environment")
    log(f"Base URL: {base_url}")
    
    all_checks_passed = True
    
    # Check homepage
    log("Checking homepage...")
    homepage_result = check_http_response(base_url)
    if not homepage_result['success']:
        log(f"Homepage check failed: {homepage_result.get('error', 'Unknown')}", 'ERROR')
        all_checks_passed = False
    else:
        log(f"✅ Homepage responding (status: {homepage_result['status_code']})")
        
        # Check content
        content_checks = check_content(homepage_result['content'], EXPECTED_CONTENT)
        for check_name, check_result in content_checks.items():
            if check_result['success']:
                log(f"✅ Content check '{check_name}': {check_result['expected']}")
            else:
                log(f"❌ Content check '{check_name}': {check_result['expected']} - NOT FOUND", 'ERROR')
                all_checks_passed = False
    
    # Check API endpoints
    log("Checking API endpoints...")
    api_results = check_api_endpoints(base_url)
    for endpoint, result in api_results.items():
        if result['success']:
            log(f"✅ Endpoint '{endpoint}': {result['status_code']}")
        else:
            log(f"❌ Endpoint '{endpoint}': {result.get('error', 'Failed')}", 'ERROR')
            all_checks_passed = False
    
    # Check deployment status endpoint
    log("Checking deployment status endpoint...")
    status_url = f"{base_url}/_deploy/status"
    status_result = check_http_response(status_url)
    if status_result['success']:
        try:
            status_data = json.loads(status_result['content'])
            log(f"✅ Deployment status: {status_data.get('environment', 'unknown')}")
        except:
            log("⚠️  Deployment status endpoint returned non-JSON", 'WARN')
    else:
        log(f"❌ Deployment status endpoint failed: {status_result.get('error', 'Unknown')}", 'ERROR')
        all_checks_passed = False
    
    return all_checks_passed

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 verify.py <env>")
        print("  env: 'dev' or 'prod'")
        sys.exit(1)
    
    env = sys.argv[1].lower()
    
    if env not in ENV_CONFIG:
        print(f"Invalid environment: {env}")
        print("Must be 'dev' or 'prod'")
        sys.exit(1)
    
    log("=" * 60)
    log("VERIFICATION STARTED")
    log("=" * 60)
    
    success = verify_environment(env)
    
    log("=" * 60)
    if success:
        log("VERIFICATION PASSED ✅")
    else:
        log("VERIFICATION FAILED ❌")
    log("=" * 60)
    
    # Output JSON result
    result = {
        'success': success,
        'environment': env,
        'timestamp': datetime.now().isoformat()
    }
    
    print("\n" + "=" * 60)
    print("VERIFICATION RESULT (JSON):")
    print(json.dumps(result, indent=2))
    print("=" * 60)
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
