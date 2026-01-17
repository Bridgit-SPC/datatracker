# Agent Deployment System - Planning Document

## Problem Statement

Current issues:
- Changes to code don't reliably appear after deployment
- No automated verification of changes
- No clear separation between dev and production
- Agents can't verify API routes and database changes
- No systematic way to promote dev → production

## Requirements

1. **Agent Capabilities**:
   - Make code changes
   - Deploy to development
   - Run automated tests (API, database, functionality)
   - Verify changes work correctly
   - Promote to production only after verification
   - Rollback if needed

2. **What Agents CANNOT Do**:
   - Visual browser verification (requires human)

3. **What Must Be Verified**:
   - Code changes are deployed
   - API routes work correctly
   - Database migrations succeed
   - Existing functionality still works
   - New functionality works as expected

## Proposed Architecture

### 1. Git Workflow

```
main (production) ← dev (development) ← feature branches
```

**Branch Strategy**:
- `main`: Production-ready code (deployed to production)
- `dev`: Development code (deployed to dev environment)
- `feature/*`: Feature branches for specific changes

**Workflow**:
1. Agent creates feature branch: `feature/fix-homepage-text`
2. Agent makes changes and commits
3. Agent merges to `dev` branch
4. Agent deploys `dev` branch to dev environment
5. Agent runs automated tests
6. If tests pass → Agent merges `dev` to `main`
7. Agent deploys `main` branch to production

### 2. Environment Structure

**Development Environment**:
- URL: `dev.rfc.themetalayer.org`
- Database: `instance_dev/datatracker_dev.db`
- Port: 8001
- Auto-deploys from `dev` branch

**Production Environment**:
- URL: `rfc.themetalayer.org`
- Database: `instance/datatracker.db`
- Port: 8000
- Auto-deploys from `main` branch

**Staging Environment** (Optional):
- URL: `staging.rfc.themetalayer.org`
- Database: `instance_staging/datatracker_staging.db`
- Port: 8002
- For final pre-production testing

### 3. Deployment System

**Components**:

1. **Deployment Script** (`deploy.py`):
   - Takes environment parameter (dev/prod)
   - Checks out correct git branch
   - Runs database migrations
   - Restarts service
   - Runs verification tests
   - Returns success/failure status

2. **Test Suite** (`tests/`):
   - Unit tests for functions
   - Integration tests for API routes
   - Database migration tests
   - End-to-end HTTP tests

3. **Verification System** (`verify.py`):
   - Tests all API endpoints
   - Verifies database schema
   - Checks expected content in responses
   - Validates no regressions

4. **Migration System** (`migrations/`):
   - Database schema changes
   - Data migrations
   - Rollback scripts

### 4. Agent Workflow

**Step-by-Step Process**:

1. **Make Changes**:
   ```bash
   git checkout -b feature/change-name
   # Make code changes
   git add .
   git commit -m "Description"
   ```

2. **Deploy to Dev**:
   ```bash
   python3 deploy.py dev
   ```
   - Checks out `dev` branch
   - Merges feature branch
   - Deploys to dev environment
   - Runs tests
   - Returns success/failure

3. **Verify in Dev**:
   ```bash
   python3 verify.py dev
   ```
   - Tests all API endpoints
   - Verifies database state
   - Checks expected changes
   - Returns detailed report

4. **Promote to Production** (only if dev verification passes):
   ```bash
   python3 deploy.py prod --from-dev
   ```
   - Merges `dev` → `main`
   - Deploys to production
   - Runs production tests
   - Creates backup
   - Returns success/failure

### 5. Testing Framework

**Test Types**:

1. **Unit Tests** (`tests/unit/`):
   - Test individual functions
   - Mock dependencies
   - Fast execution

2. **Integration Tests** (`tests/integration/`):
   - Test API endpoints
   - Test database operations
   - Test service interactions

3. **E2E Tests** (`tests/e2e/`):
   - Full HTTP requests
   - Verify responses
   - Check content

4. **Migration Tests** (`tests/migrations/`):
   - Test database migrations
   - Verify rollback works
   - Check data integrity

**Test Execution**:
```bash
# Run all tests
python3 -m pytest tests/

# Run specific test suite
python3 -m pytest tests/integration/

# Run with coverage
python3 -m pytest tests/ --cov=ietf_data_viewer_simple
```

### 6. Verification System

**What Gets Verified**:

1. **Code Deployment**:
   - Git commit hash matches deployed code
   - File timestamps match deployment time
   - Version markers in code

2. **API Routes**:
   - All routes respond correctly
   - Status codes are correct
   - Response format is valid
   - Authentication works

3. **Database**:
   - Schema matches expected state
   - Migrations applied correctly
   - Data integrity maintained
   - No orphaned records

4. **Content Verification**:
   - Expected text appears in responses
   - Expected text does NOT appear (for removals)
   - Links work correctly
   - Forms submit correctly

**Verification Script** (`verify.py`):
```python
def verify_environment(env):
    results = {
        'code_deployed': verify_code_deployment(env),
        'api_routes': verify_api_routes(env),
        'database': verify_database(env),
        'content': verify_content(env),
        'regressions': check_regressions(env)
    }
    return all(results.values()), results
```

### 7. Database Migration System

**Migration Files** (`migrations/`):
```
migrations/
  ├── 001_add_notification_level.py
  ├── 002_add_ml_number.py
  └── rollback/
      ├── 001_rollback.py
      └── 002_rollback.py
```

**Migration Format**:
```python
# migrations/003_add_new_field.py
def up(db):
    """Apply migration"""
    db.execute("ALTER TABLE user ADD COLUMN new_field VARCHAR(50)")

def down(db):
    """Rollback migration"""
    db.execute("ALTER TABLE user DROP COLUMN new_field")
```

**Migration Runner**:
- Tracks applied migrations in database
- Applies pending migrations
- Supports rollback
- Verifies migration success

### 8. Deployment Scripts

**Main Deployment Script** (`deploy.py`):

```python
def deploy(environment, branch=None):
    """
    Deploy to specified environment
    
    Args:
        environment: 'dev' or 'prod'
        branch: Git branch to deploy (defaults to env branch)
    
    Returns:
        (success: bool, details: dict)
    """
    # 1. Checkout correct branch
    # 2. Pull latest changes
    # 3. Run database migrations
    # 4. Clear cache
    # 5. Restart service
    # 6. Wait for service to be ready
    # 7. Run verification tests
    # 8. Return results
```

**Features**:
- Idempotent (can run multiple times safely)
- Atomic (all or nothing)
- Rollback capability
- Detailed logging
- Status reporting

### 9. Status and Monitoring

**Status Endpoints**:
- `/_deploy/status`: Current deployment status
- `/_deploy/version`: Git commit hash, version
- `/_deploy/health`: Service health check
- `/_deploy/migrations`: Applied migrations list

**Status Reporting**:
- JSON format for programmatic access
- Human-readable format for logs
- Error details included
- Success/failure clearly indicated

### 10. Rollback System

**Automatic Rollback**:
- If deployment fails → auto-rollback
- If tests fail → auto-rollback
- If service doesn't start → auto-rollback

**Manual Rollback**:
```bash
python3 rollback.py dev --to-commit abc123
python3 rollback.py prod --to-version 1.2.3
```

**Rollback Process**:
1. Stop service
2. Restore database backup
3. Checkout previous code version
4. Restart service
5. Verify rollback success

### 11. Backup System

**Automatic Backups**:
- Before every production deployment
- Database backup
- Code backup (git tag)
- Configuration backup

**Backup Storage**:
```
backups/
  ├── 2026-01-17_14-30-00/
  │   ├── database.db
  │   ├── git-tag.txt
  │   └── config.json
```

### 12. Agent Interface

**Simple Commands for Agents**:

```bash
# Deploy to dev
python3 deploy.py dev

# Verify dev
python3 verify.py dev

# Deploy to prod (only if dev verified)
python3 deploy.py prod

# Check status
python3 status.py dev
python3 status.py prod

# Rollback
python3 rollback.py dev
python3 rollback.py prod
```

**All Commands Return**:
- Exit code: 0 = success, 1 = failure
- JSON output: Detailed results
- Log file: Full deployment log

## Implementation Phases

### Phase 1: Core Deployment System
1. Create `deploy.py` script
2. Implement git branch checkout
3. Implement service restart
4. Basic verification (service responds)

### Phase 2: Testing Framework
1. Set up pytest
2. Create test structure
3. Write API route tests
4. Write database tests

### Phase 3: Verification System
1. Create `verify.py` script
2. Implement API verification
3. Implement content verification
4. Implement regression checks

### Phase 4: Migration System
1. Create migration framework
2. Implement migration runner
3. Add rollback capability
4. Test migration system

### Phase 5: Production Integration
1. Integrate with production
2. Add backup system
3. Add monitoring
4. Add rollback automation

## Success Criteria

1. ✅ Agent can deploy to dev with single command
2. ✅ Agent can verify deployment automatically
3. ✅ Agent can promote to prod only after verification
4. ✅ All API routes tested automatically
5. ✅ Database changes tested automatically
6. ✅ Rollback works reliably
7. ✅ No manual intervention needed (except browser check)

## Open Questions

1. Should we use a CI/CD tool (GitHub Actions, GitLab CI)?
2. Should we use Docker for environment consistency?
3. Should we use a database migration tool (Alembic)?
4. How do we handle secrets/credentials?
5. Should we add staging environment?
6. How do we handle zero-downtime deployments?

## Next Steps

1. Review and approve this plan
2. Choose testing framework (pytest recommended)
3. Choose migration tool (Alembic or custom)
4. Design test structure
5. Implement Phase 1 (Core Deployment)
6. Iterate based on feedback
