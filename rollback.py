#!/usr/bin/env python3
"""
Rollback Script - Rollback deployment to previous version

Usage:
    python3 rollback.py dev --last          # Rollback to last deployment
    python3 rollback.py prod --to-commit abc123  # Rollback to specific commit
    python3 rollback.py prod --to-tag v1.0.0    # Rollback to specific tag
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent.absolute()

ENV_CONFIG = {
    'dev': {
        'branch': 'dev',
        'service': 'datatracker-dev.service',
        'port': 8001,
        'url': 'https://dev.rfc.themetalayer.org'
    },
    'prod': {
        'branch': 'main',
        'service': 'datatracker.service',
        'port': 8000,
        'url': 'https://rfc.themetalayer.org'
    }
}

def log(message, level='INFO'):
    """Log message"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [{level}] {message}")

def run_command(cmd, check=True):
    """Run shell command"""
    log(f"Running: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=check,
            capture_output=True,
            text=True,
            cwd=SCRIPT_DIR
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        log(f"Command failed: {e}", 'ERROR')
        return False

def get_last_deployment_tag(env):
    """Get last deployment tag"""
    stdout, _ = run_command('git tag -l "deployed-*" --sort=-creatordate', capture_output=True)
    tags = stdout.strip().split('\n') if stdout else []
    return tags[0] if tags else None

def get_last_commit(env):
    """Get last commit hash"""
    stdout, _ = run_command('git rev-parse HEAD', capture_output=True)
    return stdout.strip() if stdout else None

def restore_database_backup(env):
    """Restore database from backup"""
    backup_dir = SCRIPT_DIR / 'backups'
    if not backup_dir.exists():
        log("No backups directory found", 'WARN')
        return False
    
    # Find most recent backup
    backups = sorted(backup_dir.glob('prod-*'), reverse=True)
    if not backups:
        log("No backups found", 'WARN')
        return False
    
    latest_backup = backups[0]
    db_backup = latest_backup / 'datatracker.db'
    
    if not db_backup.exists():
        log(f"No database backup in {latest_backup}", 'WARN')
        return False
    
    # Restore database
    if env == 'prod':
        db_path = SCRIPT_DIR / 'instance' / 'datatracker.db'
    else:
        db_path = SCRIPT_DIR / 'instance_dev' / 'datatracker_dev.db'
    
    import shutil
    shutil.copy2(db_backup, db_path)
    log(f"Database restored from {latest_backup}")
    return True

def rollback(env, target=None, target_type='commit'):
    """Rollback deployment"""
    if env not in ENV_CONFIG:
        log(f"Invalid environment: {env}", 'ERROR')
        return False
    
    config = ENV_CONFIG[env]
    service_name = config['service']
    port = config['port']
    
    log(f"Starting rollback for {env}")
    
    # Determine target
    if target is None:
        # Rollback to last deployment tag
        target = get_last_deployment_tag(env)
        if not target:
            log("No deployment tag found, using last commit", 'WARN')
            target = get_last_commit(env)
            target_type = 'commit'
        else:
            target_type = 'tag'
    
    if not target:
        log("Could not determine rollback target", 'ERROR')
        return False
    
    log(f"Rollback target: {target} ({target_type})")
    
    # Confirm rollback
    if env == 'prod':
        log("⚠️  WARNING: Rolling back PRODUCTION", 'WARN')
        response = input("Type 'ROLLBACK PRODUCTION' to confirm: ")
        if response != 'ROLLBACK PRODUCTION':
            log("Rollback cancelled", 'WARN')
            return False
    
    # Stage 1: Stop service
    log("Stopping service...")
    run_command(f'systemctl --user stop {service_name}')
    
    # Stage 2: Restore code
    log(f"Checking out {target_type}: {target}")
    if target_type == 'tag':
        run_command(f'git checkout {target}')
    else:
        run_command(f'git checkout {target}')
    
    # Stage 3: Restore database (production only)
    if env == 'prod':
        log("Restoring database from backup...")
        restore_database_backup(env)
    
    # Stage 4: Clear cache
    log("Clearing Python cache...")
    run_command('find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true', check=False)
    run_command('find . -type f -name "*.pyc" -delete 2>/dev/null || true', check=False)
    
    # Stage 5: Kill processes
    log(f"Killing processes on port {port}...")
    run_command(
        f"ps aux | grep python | grep {port} | awk '{{print $2}}' | xargs kill -9 2>/dev/null || true",
        check=False
    )
    
    # Stage 6: Restart service
    log("Restarting service...")
    run_command(f'systemctl --user restart {service_name}')
    
    log("=" * 60)
    log("ROLLBACK COMPLETE")
    log("=" * 60)
    log(f"Environment: {env}")
    log(f"Target: {target}")
    log(f"Service: {service_name}")
    
    return True

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 rollback.py <env> [options]")
        print("  env: 'dev' or 'prod'")
        print("  options:")
        print("    --last              Rollback to last deployment")
        print("    --to-commit <hash>  Rollback to specific commit")
        print("    --to-tag <tag>     Rollback to specific tag")
        sys.exit(1)
    
    env = sys.argv[1].lower()
    
    if env not in ENV_CONFIG:
        print(f"Invalid environment: {env}")
        sys.exit(1)
    
    # Parse options
    target = None
    target_type = 'commit'
    
    if '--last' in sys.argv:
        target = None  # Will be determined automatically
    elif '--to-commit' in sys.argv:
        idx = sys.argv.index('--to-commit')
        if idx + 1 < len(sys.argv):
            target = sys.argv[idx + 1]
            target_type = 'commit'
    elif '--to-tag' in sys.argv:
        idx = sys.argv.index('--to-tag')
        if idx + 1 < len(sys.argv):
            target = sys.argv[idx + 1]
            target_type = 'tag'
    
    success = rollback(env, target, target_type)
    
    result = {
        'success': success,
        'environment': env,
        'target': target,
        'timestamp': datetime.now().isoformat()
    }
    
    print("\n" + "=" * 60)
    print("ROLLBACK RESULT (JSON):")
    print(json.dumps(result, indent=2))
    print("=" * 60)
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
