#!/usr/bin/env python3
"""
Deployment Script - Agent-friendly deployment system for MLTF Datatracker

Usage:
    python3 deploy.py dev          # Deploy to development
    python3 deploy.py prod          # Deploy to production
    python3 deploy.py dev --branch feature/new-feature  # Deploy specific branch

Exit codes:
    0 = Success
    1 = Failure
"""

import os
import sys
import subprocess
import json
import time
import requests
from datetime import datetime
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent.absolute()
LOG_DIR = Path("/tmp")
DEPLOYMENT_LOG = LOG_DIR / f"deploy-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Environment mapping
ENV_CONFIG = {
    'dev': {
        'branch': 'dev',
        'service': 'datatracker-dev.service',
        'port': 8001,
        'url': 'https://dev.rfc.themetalayer.org',
        'flask_env': 'development'
    },
    'prod': {
        'branch': 'main',
        'service': 'datatracker.service',
        'port': 8000,
        'url': 'https://rfc.themetalayer.org',
        'flask_env': 'production'
    }
}

def log(message, level='INFO'):
    """Log message to file and stdout"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] [{level}] {message}"
    print(log_msg)
    with open(DEPLOYMENT_LOG, 'a') as f:
        f.write(log_msg + '\n')

def run_command(cmd, check=True, capture_output=False):
    """Run shell command and return result"""
    log(f"Running: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=check,
            capture_output=capture_output,
            text=True,
            cwd=SCRIPT_DIR
        )
        if capture_output:
            return result.stdout.strip(), result.returncode
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        log(f"Command failed: {e}", 'ERROR')
        if capture_output:
            return e.stdout.strip() if e.stdout else '', e.returncode
        return False

def get_current_branch():
    """Get current git branch"""
    stdout, _ = run_command('git branch --show-current', capture_output=True)
    return stdout

def get_current_commit():
    """Get current git commit hash"""
    stdout, _ = run_command('git rev-parse HEAD', capture_output=True)
    return stdout

def check_git_status():
    """Check if git repo is clean"""
    stdout, _ = run_command('git status --porcelain', capture_output=True)
    return stdout == ''

def clear_python_cache():
    """Clear Python cache files"""
    log("Clearing Python cache...")
    run_command('find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true', check=False)
    run_command('find . -type f -name "*.pyc" -delete 2>/dev/null || true', check=False)
    log("Python cache cleared")

def kill_processes_on_port(port):
    """Kill any processes using the specified port"""
    log(f"Killing processes on port {port}...")
    run_command(
        f"ps aux | grep python | grep {port} | awk '{{print $2}}' | xargs kill -9 2>/dev/null || true",
        check=False
    )
    time.sleep(1)  # Give processes time to die
    log(f"Processes on port {port} killed")

def restart_service(service_name):
    """Restart systemd service"""
    log(f"Restarting service: {service_name}")
    run_command(f'systemctl --user restart {service_name}')
    time.sleep(3)  # Give service time to start
    log(f"Service {service_name} restarted")

def check_service_status(service_name):
    """Check if service is active"""
    stdout, returncode = run_command(
        f'systemctl --user is-active {service_name}',
        check=False,
        capture_output=True
    )
    return stdout == 'active'

def wait_for_service(url, max_attempts=10, delay=2):
    """Wait for service to respond"""
    log(f"Waiting for service at {url}...")
    for i in range(max_attempts):
        try:
            response = requests.get(url, timeout=5, verify=False)
            if response.status_code == 200:
                log(f"Service is responding (attempt {i+1}/{max_attempts})")
                return True
        except Exception as e:
            log(f"Service not ready yet (attempt {i+1}/{max_attempts}): {e}", 'WARN')
        time.sleep(delay)
    log("Service did not respond in time", 'ERROR')
    return False

def create_backup(env):
    """Create backup before production deployment"""
    if env != 'prod':
        log("Skipping backup (not production)")
        return True
    
    log("Creating production backup...")
    backup_dir = SCRIPT_DIR / 'backups' / f'prod-{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Backup database
    db_path = SCRIPT_DIR / 'instance' / 'datatracker.db'
    if db_path.exists():
        import shutil
        shutil.copy2(db_path, backup_dir / 'datatracker.db')
        log("Database backed up")
    
    # Backup service file
    service_file = Path.home() / '.config' / 'systemd' / 'user' / 'datatracker.service'
    if service_file.exists():
        import shutil
        shutil.copy2(service_file, backup_dir / 'datatracker.service')
        log("Service file backed up")
    
    # Save git state
    commit = get_current_commit()
    branch = get_current_branch()
    with open(backup_dir / 'git-state.txt', 'w') as f:
        f.write(f"Commit: {commit}\nBranch: {branch}\n")
    
    log(f"Backup created: {backup_dir}")
    return True

def deploy(env, branch=None):
    """Main deployment function"""
    if env not in ENV_CONFIG:
        log(f"Invalid environment: {env}. Must be 'dev' or 'prod'", 'ERROR')
        return False
    
    config = ENV_CONFIG[env]
    target_branch = branch or config['branch']
    service_name = config['service']
    port = config['port']
    url = config['url']
    
    log(f"Starting deployment to {env}")
    log(f"Target branch: {target_branch}")
    log(f"Service: {service_name}")
    log(f"Port: {port}")
    log(f"URL: {url}")
    
    # Stage 1: Pre-Deployment Checks
    log("=" * 60)
    log("Stage 1: Pre-Deployment Checks")
    log("=" * 60)
    
    # Check git status
    if not check_git_status():
        log("WARNING: Uncommitted changes detected", 'WARN')
        log("Continuing anyway...", 'WARN')
    
    # Check current branch
    current_branch = get_current_branch()
    log(f"Current branch: {current_branch}")
    
    # Create backup for production
    if env == 'prod':
        if not create_backup(env):
            log("Backup failed, aborting", 'ERROR')
            return False
    
    # Stage 2: Deployment
    log("=" * 60)
    log("Stage 2: Deployment")
    log("=" * 60)
    
    # Checkout target branch
    if current_branch != target_branch:
        log(f"Switching to branch: {target_branch}")
        if not run_command(f'git checkout {target_branch}'):
            log(f"Failed to checkout branch {target_branch}", 'ERROR')
            return False
    
    # Pull latest changes
    log("Pulling latest changes...")
    if not run_command('git pull'):
        log("Failed to pull latest changes", 'ERROR')
        return False
    
    # Get commit hash
    commit_hash = get_current_commit()
    log(f"Deploying commit: {commit_hash[:8]}")
    
    # Clear Python cache
    clear_python_cache()
    
    # Kill existing processes
    kill_processes_on_port(port)
    
    # Restart service
    restart_service(service_name)
    
    # Stage 3: Verification
    log("=" * 60)
    log("Stage 3: Verification")
    log("=" * 60)
    
    # Check service status
    if not check_service_status(service_name):
        log(f"Service {service_name} is not active", 'ERROR')
        return False
    
    # Wait for service to respond
    if not wait_for_service(url):
        log("Service did not respond", 'ERROR')
        return False
    
    # Stage 4: Post-Deployment
    log("=" * 60)
    log("Stage 4: Post-Deployment")
    log("=" * 60)
    
    # Create git tag for production
    if env == 'prod':
        tag_name = f"deployed-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        run_command(f'git tag {tag_name}', check=False)
        log(f"Created tag: {tag_name}")
    
    log("=" * 60)
    log("DEPLOYMENT COMPLETE")
    log("=" * 60)
    log(f"Environment: {env}")
    log(f"Branch: {target_branch}")
    log(f"Commit: {commit_hash[:8]}")
    log(f"URL: {url}")
    log(f"Log file: {DEPLOYMENT_LOG}")
    
    return True

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 deploy.py <env> [--branch <branch>]")
        print("  env: 'dev' or 'prod'")
        print("  branch: Optional branch name (defaults to env branch)")
        sys.exit(1)
    
    env = sys.argv[1].lower()
    branch = None
    
    # Parse --branch flag
    if '--branch' in sys.argv:
        idx = sys.argv.index('--branch')
        if idx + 1 < len(sys.argv):
            branch = sys.argv[idx + 1]
    
    # Initialize log file
    DEPLOYMENT_LOG.parent.mkdir(exist_ok=True)
    with open(DEPLOYMENT_LOG, 'w') as f:
        f.write(f"Deployment log started at {datetime.now()}\n")
        f.write(f"Environment: {env}\n")
        f.write(f"Branch: {branch or 'default'}\n")
        f.write("=" * 60 + "\n")
    
    # Run deployment
    success = deploy(env, branch)
    
    # Output JSON result for agent parsing
    result = {
        'success': success,
        'environment': env,
        'branch': branch or ENV_CONFIG[env]['branch'],
        'commit': get_current_commit(),
        'log_file': str(DEPLOYMENT_LOG),
        'timestamp': datetime.now().isoformat()
    }
    
    print("\n" + "=" * 60)
    print("DEPLOYMENT RESULT (JSON):")
    print(json.dumps(result, indent=2))
    print("=" * 60)
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
