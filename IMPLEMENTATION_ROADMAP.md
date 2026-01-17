# Implementation Roadmap - Agent Deployment System

## Current State Analysis

### What We Have:
- ✅ Separate dev/prod environments (different databases, ports)
- ✅ Systemd services for both environments
- ✅ Nginx reverse proxy for both
- ✅ Git repository
- ✅ Basic deployment scripts (but unreliable)

### What's Missing:
- ❌ Reliable deployment verification
- ❌ Automated testing framework
- ❌ Database migration system
- ❌ API route testing
- ❌ Content verification
- ❌ Git workflow enforcement
- ❌ Rollback capability
- ❌ Status monitoring

## Proposed Solution Architecture

### 1. Git Workflow (Simplified)

**Current**: Single `main` branch
**Proposed**: Two-branch system

```
main (production)
  ↑
dev (development)
  ↑
feature/* (temporary)
```

**Workflow**:
1. Agent creates `feature/change-name` branch
2. Makes changes, commits
3. Merges to `dev` → auto-deploys to dev environment
4. Agent runs verification
5. If verified → merges `dev` to `main` → auto-deploys to prod

**Benefits**:
- Clear separation of dev/prod code
- Can test multiple features in dev before promoting
- Easy rollback (just revert merge)

### 2. Deployment Pipeline

**Stage 1: Pre-Deployment**
- Check git branch matches environment
- Verify no uncommitted changes
- Create backup (prod only)
- Check service dependencies

**Stage 2: Deployment**
- Checkout correct branch
- Pull latest changes
- Run database migrations
- Clear Python cache
- Restart service
- Wait for service health check

**Stage 3: Verification**
- Test service responds
- Test all API endpoints
- Verify database state
- Check expected content
- Run regression tests

**Stage 4: Post-Deployment**
- Log deployment details
- Update status endpoint
- Send notification (optional)
- Create git tag (prod only)

### 3. Testing Framework

**Structure**:
```
tests/
  ├── unit/
  │   ├── test_models.py
  │   ├── test_utils.py
  │   └── test_helpers.py
  ├── integration/
  │   ├── test_api_routes.py
  │   ├── test_database.py
  │   └── test_auth.py
  ├── e2e/
  │   ├── test_homepage.py
  │   ├── test_document_flow.py
  │   └── test_comment_system.py
  └── migrations/
      └── test_migrations.py
```

**Test Types**:

1. **Unit Tests**: Fast, isolated function tests
2. **Integration Tests**: API + database interaction tests
3. **E2E Tests**: Full HTTP request/response tests
4. **Migration Tests**: Database schema change tests

**Test Execution**:
```bash
# Run all tests
pytest tests/

# Run specific suite
pytest tests/integration/

# Run with coverage
pytest tests/ --cov=ietf_data_viewer_simple --cov-report=html
```

### 4. Verification System

**What Gets Verified**:

1. **Service Health**:
   - Service is running
   - Port is listening
   - HTTP responds with 200

2. **API Routes** (all routes):
   - GET / → 200, contains expected content
   - GET /doc/all/ → 200, returns document list
   - GET /doc/draft/{name}/ → 200, returns draft details
   - POST /login/ → 302 redirect on success
   - All other routes tested

3. **Database**:
   - Schema matches expected
   - Migrations applied
   - Data integrity checks
   - No errors in queries

4. **Content**:
   - Expected text appears
   - Expected text removed (for deletions)
   - Links work
   - Forms work

5. **Regressions**:
   - Existing functionality still works
   - No broken links
   - No JavaScript errors (if applicable)

**Verification Script**:
```python
# verify.py
def verify_environment(env):
    results = {
        'service': verify_service(env),
        'api_routes': verify_all_routes(env),
        'database': verify_database(env),
        'content': verify_content(env),
        'regressions': check_regressions(env)
    }
    
    if all(results.values()):
        return True, results
    else:
        return False, results
```

### 5. Database Migration System

**Migration Format**:
```python
# migrations/001_add_field.py
"""
Migration: Add notification_level to user_follow
Date: 2026-01-17
"""

def up(db):
    """Apply migration"""
    db.execute("""
        ALTER TABLE user_follow 
        ADD COLUMN notification_level VARCHAR(20) DEFAULT 'all'
    """)

def down(db):
    """Rollback migration"""
    db.execute("""
        ALTER TABLE user_follow 
        DROP COLUMN notification_level
    """)
```

**Migration Tracking**:
- Store applied migrations in `migrations` table
- Track migration order
- Support rollback
- Verify before/after state

**Migration Runner**:
```python
# migrations/runner.py
def apply_migrations(db, target_env):
    """Apply pending migrations"""
    # 1. Get list of applied migrations
    # 2. Find pending migrations
    # 3. Apply each in order
    # 4. Record in migrations table
    # 5. Verify success
```

### 6. Agent Commands

**Simple Interface**:

```bash
# Deploy to dev (from current branch)
python3 deploy.py dev

# Deploy to dev (from specific branch)
python3 deploy.py dev --branch feature/new-feature

# Verify dev environment
python3 verify.py dev

# Deploy to prod (only if dev verified)
python3 deploy.py prod

# Check status
python3 status.py dev
python3 status.py prod

# Rollback
python3 rollback.py dev
python3 rollback.py prod

# Run tests only
pytest tests/
```

**Command Output Format**:
- Exit code: 0 = success, 1 = failure
- JSON output: `{"success": true, "details": {...}}`
- Log file: `/tmp/deploy-{env}-{timestamp}.log`

### 7. Status Endpoints

**Built into Application**:

```python
@app.route('/_deploy/status')
def deployment_status():
    """Return deployment status"""
    return jsonify({
        'environment': ENV,
        'git_branch': get_current_branch(),
        'git_commit': get_current_commit(),
        'deployed_at': get_deployment_time(),
        'service_status': check_service_status(),
        'database_version': get_database_version(),
        'migrations_applied': get_applied_migrations()
    })

@app.route('/_deploy/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'database': check_database_connection(),
        'service': check_service_health()
    })
```

### 8. Rollback System

**Automatic Rollback Triggers**:
- Service fails to start
- Health check fails after deployment
- Tests fail after deployment
- Database migration fails

**Manual Rollback**:
```bash
# Rollback to previous commit
python3 rollback.py dev --to-commit abc123

# Rollback to previous version tag
python3 rollback.py prod --to-version v1.2.3

# Rollback last deployment
python3 rollback.py dev --last
```

**Rollback Process**:
1. Stop service
2. Restore database from backup
3. Checkout previous code version
4. Restart service
5. Verify rollback success
6. Log rollback event

### 9. Backup System

**Automatic Backups**:
- Before every production deployment
- Database backup (SQL dump)
- Code backup (git tag)
- Configuration backup

**Backup Format**:
```
backups/
  └── prod/
      └── 2026-01-17_14-30-00/
          ├── database.sql
          ├── git-tag.txt
          └── config.json
```

**Backup Retention**:
- Keep last 10 production backups
- Keep last 5 dev backups
- Compress old backups

### 10. Monitoring and Logging

**Deployment Logs**:
- All deployments logged to `/var/log/datatracker/deployments.log`
- Each deployment gets unique ID
- Log includes: timestamp, environment, git commit, results

**Status Monitoring**:
- Service health endpoint
- Database connection status
- Recent deployments list
- Error tracking

## Implementation Phases

### Phase 1: Core Deployment (Week 1)
**Goal**: Reliable deployment to dev and prod

**Tasks**:
1. Create `deploy.py` script
2. Implement git branch checkout
3. Implement service restart with verification
4. Add basic health checks
5. Create status endpoints

**Deliverables**:
- `deploy.py` script
- `status.py` script
- Status endpoints in app
- Basic health checks

### Phase 2: Testing Framework (Week 2)
**Goal**: Automated testing of all functionality

**Tasks**:
1. Set up pytest framework
2. Create test structure
3. Write API route tests
4. Write database tests
5. Write content verification tests

**Deliverables**:
- `tests/` directory structure
- Test suite for all API routes
- Test suite for database operations
- Coverage reporting

### Phase 3: Verification System (Week 2-3)
**Goal**: Comprehensive verification after deployment

**Tasks**:
1. Create `verify.py` script
2. Implement API route verification
3. Implement content verification
4. Implement regression checks
5. Integrate with deployment script

**Deliverables**:
- `verify.py` script
- Verification test suite
- Integration with deploy.py

### Phase 4: Migration System (Week 3)
**Goal**: Safe database schema changes

**Tasks**:
1. Create migration framework
2. Implement migration runner
3. Add rollback capability
4. Create migration tests
5. Document migration process

**Deliverables**:
- `migrations/` directory
- Migration runner script
- Rollback scripts
- Migration documentation

### Phase 5: Production Integration (Week 4)
**Goal**: Complete production-ready system

**Tasks**:
1. Integrate all components
2. Add backup system
3. Add monitoring
4. Add rollback automation
5. End-to-end testing

**Deliverables**:
- Complete deployment system
- Backup automation
- Monitoring dashboard
- Documentation

## Success Metrics

1. **Deployment Reliability**: 100% success rate
2. **Test Coverage**: >80% code coverage
3. **Verification Time**: <2 minutes for full verification
4. **Rollback Time**: <5 minutes for complete rollback
5. **Zero Downtime**: Production deployments with zero downtime

## Risk Mitigation

1. **Deployment Failures**:
   - Automatic rollback on failure
   - Detailed error logging
   - Pre-deployment validation

2. **Database Issues**:
   - Migrations tested in dev first
   - Automatic backups before migrations
   - Rollback scripts for all migrations

3. **Service Issues**:
   - Health checks before/after deployment
   - Automatic service restart on failure
   - Monitoring and alerting

4. **Code Issues**:
   - Tests must pass before production
   - Code review process (if needed)
   - Staged rollouts

## Open Questions

1. **CI/CD Tool**: Should we use GitHub Actions/GitLab CI or keep it simple?
   - **Recommendation**: Start simple, add CI/CD later if needed

2. **Docker**: Should we containerize for consistency?
   - **Recommendation**: Not needed initially, add if scaling

3. **Migration Tool**: Use Alembic or custom solution?
   - **Recommendation**: Custom solution for SQLite simplicity

4. **Staging Environment**: Do we need staging?
   - **Recommendation**: Start with dev/prod, add staging if needed

5. **Zero-Downtime**: How to achieve zero-downtime deployments?
   - **Recommendation**: Use blue-green deployment or rolling restart

6. **Secrets Management**: How to handle credentials?
   - **Recommendation**: Environment variables, consider vault later

## Next Steps

1. **Review this plan** with stakeholders
2. **Approve approach** and timeline
3. **Start Phase 1** implementation
4. **Iterate** based on feedback
5. **Document** as we go

## Notes

- This is a **planning document** - no code yet
- Implementation should be **iterative**
- **Test everything** before production
- **Document** all processes
- **Keep it simple** - avoid over-engineering
