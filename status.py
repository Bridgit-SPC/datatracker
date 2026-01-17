#!/usr/bin/env python3
"""
Status Script - Check deployment status for MLTF Datatracker

Usage:
    python3 status.py dev          # Check development status
    python3 status.py prod         # Check production status
    python3 status.py all          # Check both environments
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
        'service': 'datatracker-dev.service',
        'port': 8001,
        'url': 'https://dev.rfc.themetalayer.org',
        'flask_env': 'development'
    },
    'prod': {
        'service': 'datatracker.service',
        'port': 8000,
        'url': 'https://rfc.themetalayer.org',
        'flask_env': 'production'
    }
}

def run_command(cmd, capture_output=True):
    """Run shell command and return result"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=capture_output,
            text=True,
            cwd=SCRIPT_DIR,
            timeout=5
        )
        if capture_output:
            return result.stdout.strip(), result.returncode == 0
        return result.returncode == 0
    except Exception as e:
        return '', False

def get_git_info():
    """Get git branch and commit"""
    branch, _ = run_command('git branch --show-current')
    commit, _ = run_command('git rev-parse HEAD')
    commit_short = commit[:8] if commit else 'unknown'
    return {
        'branch': branch or 'unknown',
        'commit': commit or 'unknown',
        'commit_short': commit_short
    }

def check_service_status(service_name):
    """Check systemd service status"""
    stdout, success = run_command(f'systemctl --user is-active {service_name}')
    is_active = stdout == 'active'
    
    # Get more details
    status_output, _ = run_command(f'systemctl --user status {service_name} --no-pager -l')
    
    return {
        'active': is_active,
        'status': stdout or 'unknown',
        'details': status_output[:500] if status_output else ''
    }

def check_http_status(url):
    """Check HTTP endpoint status"""
    try:
        response = requests.get(url, timeout=5, verify=False)
        return {
            'status_code': response.status_code,
            'responding': response.status_code == 200,
            'response_time': response.elapsed.total_seconds()
        }
    except Exception as e:
        return {
            'status_code': None,
            'responding': False,
            'error': str(e)
        }

def check_deployment_endpoint(url):
    """Check deployment status endpoint"""
    try:
        response = requests.get(f'{url}/_deploy/status', timeout=5, verify=False)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        return {'error': str(e)}

def check_database(env):
    """Check database file exists"""
    if env == 'dev':
        db_path = SCRIPT_DIR / 'instance_dev' / 'datatracker_dev.db'
    else:
        db_path = SCRIPT_DIR / 'instance' / 'datatracker.db'
    
    if db_path.exists():
        size = db_path.stat().st_size
        return {
            'exists': True,
            'path': str(db_path),
            'size': size,
            'size_mb': round(size / 1024 / 1024, 2)
        }
    return {'exists': False, 'path': str(db_path)}

def get_status(env):
    """Get comprehensive status for environment"""
    if env not in ENV_CONFIG:
        return None
    
    config = ENV_CONFIG[env]
    service_name = config['service']
    url = config['url']
    
    git_info = get_git_info()
    service_status = check_service_status(service_name)
    http_status = check_http_status(url)
    deployment_info = check_deployment_endpoint(url)
    db_info = check_database(env)
    
    return {
        'environment': env,
        'timestamp': datetime.now().isoformat(),
        'git': git_info,
        'service': {
            'name': service_name,
            **service_status
        },
        'http': {
            'url': url,
            **http_status
        },
        'deployment': deployment_info,
        'database': db_info
    }

def print_status(status):
    """Print status in human-readable format"""
    if not status:
        print(f"❌ Invalid environment")
        return
    
    print("=" * 60)
    print(f"Status: {status['environment'].upper()}")
    print("=" * 60)
    print(f"Timestamp: {status['timestamp']}")
    print()
    
    # Git info
    print("Git:")
    print(f"  Branch: {status['git']['branch']}")
    print(f"  Commit: {status['git']['commit_short']}")
    print()
    
    # Service status
    print("Service:")
    service_icon = "✅" if status['service']['active'] else "❌"
    print(f"  {service_icon} {status['service']['name']}: {status['service']['status']}")
    print()
    
    # HTTP status
    print("HTTP:")
    http_icon = "✅" if status['http']['responding'] else "❌"
    print(f"  {http_icon} {status['http']['url']}")
    if status['http']['responding']:
        print(f"  Status Code: {status['http']['status_code']}")
        print(f"  Response Time: {status['http']['response_time']:.2f}s")
    else:
        print(f"  Error: {status['http'].get('error', 'Unknown')}")
    print()
    
    # Database
    print("Database:")
    db_icon = "✅" if status['database']['exists'] else "❌"
    print(f"  {db_icon} {status['database']['path']}")
    if status['database']['exists']:
        print(f"  Size: {status['database']['size_mb']} MB")
    print()
    
    # Deployment endpoint
    if status['deployment']:
        print("Deployment Endpoint:")
        if 'error' not in status['deployment']:
            print(f"  ✅ Responding")
            print(f"  Environment: {status['deployment'].get('environment', 'unknown')}")
            print(f"  Port: {status['deployment'].get('port', 'unknown')}")
        else:
            print(f"  ❌ Error: {status['deployment']['error']}")
        print()

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 status.py <env>")
        print("  env: 'dev', 'prod', or 'all'")
        sys.exit(1)
    
    env_arg = sys.argv[1].lower()
    
    if env_arg == 'all':
        envs = ['dev', 'prod']
    elif env_arg in ENV_CONFIG:
        envs = [env_arg]
    else:
        print(f"Invalid environment: {env_arg}")
        print("Must be 'dev', 'prod', or 'all'")
        sys.exit(1)
    
    results = {}
    for env in envs:
        status = get_status(env)
        results[env] = status
        print_status(status)
    
    # Output JSON for agent parsing
    print("=" * 60)
    print("JSON OUTPUT:")
    print(json.dumps(results, indent=2))
    
    # Exit code based on overall health
    all_healthy = all(
        results[env]['service']['active'] and results[env]['http']['responding']
        for env in results
    )
    sys.exit(0 if all_healthy else 1)

if __name__ == '__main__':
    main()
