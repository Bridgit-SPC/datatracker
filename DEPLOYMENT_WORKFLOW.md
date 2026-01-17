# Deployment Workflow - Agent Guide

## Overview

This document describes the agent-friendly deployment workflow for the MLTF Datatracker.

## Quick Start

### Deploy to Development
```bash
python3 deploy.py dev
python3 verify.py dev
```

### Deploy to Production (after dev verified)
```bash
python3 deploy.py prod
python3 verify.py prod
```

### Check Status
```bash
python3 status.py dev
python3 status.py prod
python3 status.py all
```

### Rollback (if needed)
```bash
python3 rollback.py dev --last
python3 rollback.py prod --to-commit abc123
```

## Detailed Workflow

### Phase 1: Development

1. **Make changes in dev branch**
   ```bash
   git checkout dev
   # Make code changes
   git add .
   git commit -m "Description of changes"
   ```

2. **Deploy to dev environment**
   ```bash
   python3 deploy.py dev
   ```
   
   This will:
   - Checkout dev branch
   - Pull latest changes
   - Clear Python cache
   - Restart dev service
   - Wait for service to respond

3. **Verify deployment**
   ```bash
   python3 verify.py dev
   ```
   
   This checks:
   - Service is responding
   - Homepage loads correctly
   - Expected content is present
   - API endpoints work

4. **Check status**
   ```bash
   python3 status.py dev
   ```

### Phase 2: Production (Only After Dev Verified)

1. **Merge dev to main**
   ```bash
   git checkout main
   git merge dev
   git push origin main
   ```

2. **Deploy to production**
   ```bash
   python3 deploy.py prod
   ```
   
   This will:
   - Create backup (database + service files)
   - Checkout main branch
   - Pull latest changes
   - Clear Python cache
   - Restart production service
   - Wait for service to respond
   - Create deployment tag

3. **Verify production**
   ```bash
   python3 verify.py prod
   ```

4. **Monitor**
   ```bash
   python3 status.py prod
   ```

## Scripts Reference

### deploy.py

**Purpose**: Deploy code to an environment

**Usage**:
```bash
python3 deploy.py <env> [--branch <branch>]
```

**Examples**:
```bash
python3 deploy.py dev
python3 deploy.py prod
python3 deploy.py dev --branch feature/new-feature
```

**Output**: JSON result with success status, commit hash, log file location

**Exit Codes**:
- `0` = Success
- `1` = Failure

### verify.py

**Purpose**: Verify deployment after changes

**Usage**:
```bash
python3 verify.py <env>
```

**Checks**:
- HTTP response (status 200)
- Expected content on homepage
- API endpoints responding
- Deployment status endpoint

**Output**: JSON result with verification status

**Exit Codes**:
- `0` = All checks passed
- `1` = One or more checks failed

### status.py

**Purpose**: Check current status of environment(s)

**Usage**:
```bash
python3 status.py <env>
python3 status.py all
```

**Shows**:
- Git branch and commit
- Service status (active/inactive)
- HTTP response status
- Database status
- Deployment endpoint info

**Output**: Human-readable + JSON

**Exit Codes**:
- `0` = All environments healthy
- `1` = One or more unhealthy

### rollback.py

**Purpose**: Rollback to previous version

**Usage**:
```bash
python3 rollback.py <env> --last
python3 rollback.py <env> --to-commit <hash>
python3 rollback.py <env> --to-tag <tag>
```

**Process**:
1. Stop service
2. Checkout target commit/tag
3. Restore database (prod only)
4. Clear cache
5. Restart service

**Safety**: Requires confirmation for production rollback

## API Endpoints

### `/_deploy/status`

**Method**: GET  
**Purpose**: Get deployment status  
**Response**: JSON with environment, git info, service status, database info

### `/_deploy/health`

**Method**: GET  
**Purpose**: Health check  
**Response**: JSON with overall health status  
**Status Codes**: 200 (healthy), 503 (unhealthy)

## Environment Configuration

### Development
- **Branch**: `dev`
- **Service**: `datatracker-dev.service`
- **Port**: 8001
- **URL**: `https://dev.rfc.themetalayer.org`
- **Database**: `instance_dev/datatracker_dev.db`

### Production
- **Branch**: `main`
- **Service**: `datatracker.service`
- **Port**: 8000
- **URL**: `https://rfc.themetalayer.org`
- **Database**: `instance/datatracker.db`

## Best Practices

1. **Always test in dev first**
   - Deploy to dev
   - Verify in dev
   - Only then deploy to prod

2. **Use verification**
   - Always run `verify.py` after deployment
   - Don't skip verification steps

3. **Check status regularly**
   - Use `status.py` to monitor environments
   - Check before and after deployments

4. **Keep backups**
   - Production deployments create automatic backups
   - Don't delete backups until system is stable

5. **Use rollback if needed**
   - If verification fails, rollback immediately
   - Don't try to fix in production

## Troubleshooting

### Service won't start
```bash
# Check service status
systemctl --user status datatracker-dev.service

# Check logs
journalctl --user -u datatracker-dev.service -n 50

# Manual restart
systemctl --user restart datatracker-dev.service
```

### Code changes not appearing
```bash
# Clear cache manually
find . -type d -name __pycache__ -exec rm -r {} +
find . -type f -name "*.pyc" -delete

# Kill processes
ps aux | grep python | grep 8001 | awk '{print $2}' | xargs kill -9

# Restart service
systemctl --user restart datatracker-dev.service
```

### Database issues
```bash
# Check database exists
ls -lh instance_dev/datatracker_dev.db

# Check database permissions
ls -l instance_dev/

# Restore from backup (if needed)
cp backups/prod-YYYYMMDD_HHMMSS/datatracker.db instance/datatracker.db
```

## Agent Integration

### For Agents

All scripts output JSON for easy parsing:

```python
import subprocess
import json

result = subprocess.run(['python3', 'deploy.py', 'dev'], 
                       capture_output=True, text=True)
# Parse JSON from output
```

Exit codes indicate success/failure:
- `0` = Success
- `1` = Failure

Log files are written to `/tmp/deploy-YYYYMMDD_HHMMSS.log`

### Example Agent Workflow

```python
# 1. Deploy to dev
result = subprocess.run(['python3', 'deploy.py', 'dev'])
if result.returncode != 0:
    # Handle failure
    return

# 2. Verify dev
result = subprocess.run(['python3', 'verify.py', 'dev'])
if result.returncode != 0:
    # Rollback dev
    subprocess.run(['python3', 'rollback.py', 'dev', '--last'])
    return

# 3. Deploy to prod
result = subprocess.run(['python3', 'deploy.py', 'prod'])
if result.returncode != 0:
    # Rollback prod
    subprocess.run(['python3', 'rollback.py', 'prod', '--last'])
    return

# 4. Verify prod
result = subprocess.run(['python3', 'verify.py', 'prod'])
if result.returncode != 0:
    # Rollback prod
    subprocess.run(['python3', 'rollback.py', 'prod', '--last'])
    return

# Success!
```

## References

- `IMPLEMENTATION_ROADMAP.md` - Detailed implementation plan
- `AGENT_DEPLOYMENT_PLAN.md` - High-level architecture
- `SAFE_MIGRATION_PLAN.md` - Migration strategy
- `JAUmemory_RECORDS.md` - Project memory and patterns
