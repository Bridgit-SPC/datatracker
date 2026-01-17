# JAUmemory Records - MLTF Datatracker RFC Project

This file serves as a memory store for the MLTF Datatracker project. Key decisions, patterns, and learnings are documented here for future reference.

## Project Context

**Project**: MLTF Datatracker (RFC App)  
**Purpose**: Governance hub for Meta-Layer Task Force standards  
**Tech Stack**: Flask, SQLite, Bootstrap, systemd, Nginx  
**Environments**: Production (`rfc.themetalayer.org`), Development (`dev.rfc.themetalayer.org`)

## Current Architecture

### Deployment System (2026-01-17)

**Decision**: Implement agent-friendly CI/CD system  
**Rationale**: Previous deployment failures (code changes not appearing) require reliable, automated system  
**Status**: In progress

**Key Components**:
- Git workflow: `main` (prod) ← `dev` (dev) ← `feature/*` (temp)
- Deployment scripts: `deploy.py`, `verify.py`, `status.py`, `rollback.py`
- Testing framework: Unit, integration, E2E tests
- Database migrations: Manual SQL + Alembic (future)

**Pattern**: Environment-based configuration
- Use `FLASK_ENV` to determine environment
- Separate databases: `instance/datatracker.db` (prod), `instance_dev/datatracker_dev.db` (dev)
- Separate ports: 8000 (prod), 8001 (dev)
- Separate systemd services: `datatracker.service`, `datatracker-dev.service`

## Key Patterns

### Pattern: Environment-based Configuration
**Use Case**: Different settings for dev/prod  
**Implementation**: 
```python
ENV = os.environ.get('FLASK_ENV', 'production').lower()
if ENV == 'development':
    INSTANCE_DIR = 'instance_dev'
    DB_NAME = 'datatracker_dev.db'
    PORT = 8001
    DEBUG = True
else:
    INSTANCE_DIR = 'instance'
    DB_NAME = 'datatracker.db'
    PORT = 8000
    DEBUG = False
```
**Benefits**: Same codebase, different behavior. Easy to switch environments.  
**Location**: `ietf_data_viewer_simple.py` lines 89-104

### Pattern: Safe Migration
**Use Case**: Deploy new systems without breaking production  
**Implementation**:
1. Create backups (database, service files, git state)
2. Tag production state in git
3. Create dev branch
4. Implement in dev branch only
5. Test thoroughly in dev
6. Merge to main when ready
**Benefits**: Zero-risk deployment, easy rollback  
**Location**: `SAFE_MIGRATION_PLAN.md`, `safe-migration.sh`

### Pattern: Time-based Permissions
**Use Case**: Allow edit/delete within time window  
**Implementation**: Check `edited_at` timestamp, compare to current time  
**Example**: Comment edit/delete within 15 minutes  
**Location**: `can_edit_delete_comment()` function

### Pattern: Soft Delete
**Use Case**: Preserve data while marking as deleted  
**Implementation**: `is_deleted` boolean flag, store `original_text`  
**Benefits**: Audit trail, can restore if needed  
**Location**: `Comment` model

## Common Issues and Solutions

### Issue: Code changes not appearing after deployment
**Symptoms**: Changes in file but not visible in browser  
**Cause**: Python cache (.pyc files) or service not restarting properly  
**Solution**: 
1. Clear `__pycache__` directories: `find . -type d -name __pycache__ -exec rm -r {} +`
2. Kill processes: `ps aux | grep python | grep PORT | awk '{print $2}' | xargs kill -9`
3. Restart service: `systemctl --user restart datatracker-dev.service`
**Prevention**: Always use `deploy.py` script which clears cache automatically  
**Date**: 2026-01-17

### Issue: Flask reloader hanging in systemd
**Symptoms**: Service starts but hangs, no response  
**Cause**: Flask's debug reloader conflicts with systemd  
**Solution**: Disable reloader when `INVOCATION_ID` (systemd env var) is present:
```python
use_reloader = DEBUG and not os.environ.get('INVOCATION_ID')
app.run(use_reloader=use_reloader)
```
**Prevention**: Always check for systemd environment  
**Date**: 2026-01-17

### Issue: Database schema out of sync
**Symptoms**: `OperationalError: no such column: X`  
**Cause**: Model changed but database not migrated  
**Solution**: 
1. Add column manually: `ALTER TABLE table_name ADD COLUMN column_name TYPE;`
2. Or recreate: `db.drop_all()` then `db.create_all()` (loses data!)
**Prevention**: Use proper migrations (Alembic planned)  
**Date**: 2026-01-17

### Issue: Development environment not updating
**Symptoms**: Code changes not visible in dev, despite restarts  
**Cause**: Multiple issues - cache, wrong branch, service not restarting  
**Solution**: Comprehensive fix script:
1. Kill all Python processes on port
2. Clear all cache
3. Verify git branch
4. Restart service
5. Test HTTP response
**Prevention**: Use reliable deployment script with verification  
**Date**: 2026-01-17

## Feature Implementations

### Feature: Comment Edit/Delete
**Purpose**: Allow users to edit/delete their own comments within 15 minutes  
**Implementation**: 
- Added `edited_at`, `is_deleted`, `original_text` columns to `Comment` model
- Added `can_edit_delete_comment()` function
- Added routes `/doc/draft/<draft_name>/comments/<comment_id>/edit` and `/delete`
- Updated `render_comment_tree()` to show Edit/Delete buttons conditionally
**Components**: `ietf_data_viewer_simple.py` (Comment model, routes, render_comment_tree)  
**Patterns**: Time-based permission check, soft delete pattern  
**Lessons**: Need to check both author and time limit. Store original_text for audit.  
**Related**: Comment system, User permissions  
**Date**: 2026-01-17

### Feature: ML Number Assignment
**Purpose**: Assign sequential ML numbers (ML-001, ML-002, ..., ML-999, ML-1000+)  
**Implementation**: 
- Added `ml_number` column to `Submission` model
- Created `get_next_ml_number()` function
- Format: `ML-{num:03d}` for 1-999, `ML-{num:04d}` for 1000+
- Assigned on approval: `approve_submission()` calls `get_next_ml_number()`
**Components**: `ietf_data_viewer_simple.py` (Submission model, get_next_ml_number, approve_submission)  
**Patterns**: Sequential ID generation  
**Lessons**: Format changes at 1000 to accommodate growth  
**Date**: 2026-01-17

### Feature: Document Follow System
**Purpose**: Allow users to follow documents and receive notifications  
**Implementation**: 
- `UserFollow` model with `notification_level` (all/significant/major/comments/none)
- Routes for follow/unfollow
- Functions: `get_user_follow()`, `should_notify_user()`, `get_users_to_notify()`
**Components**: `ietf_data_viewer_simple.py` (UserFollow model, routes, notification functions)  
**Patterns**: Many-to-many relationship, notification levels  
**Status**: Email notifications not yet implemented  
**Date**: 2026-01-17

### Feature: Environment Separation
**Purpose**: Separate development and production environments  
**Implementation**: 
- Environment-based config using `FLASK_ENV`
- Separate databases, ports, systemd services
- Separate Nginx configs
- SSL certificates for both domains
**Components**: `ietf_data_viewer_simple.py`, systemd services, Nginx configs  
**Patterns**: Environment-based configuration  
**Lessons**: Critical for safe development and testing  
**Date**: 2026-01-17

## Database Patterns

### Pattern: ML Number Format
**Use Case**: Sequential document numbering  
**Format**: `ML-001` to `ML-999`, then `ML-1000`+  
**Query**: `SELECT MAX(ml_number) FROM submission WHERE ml_number IS NOT NULL`  
**Migration**: Added column, assigned `ML-0001` to existing approved submission  
**Date**: 2026-01-17

### Pattern: Comment Tree Structure
**Use Case**: Nested comments/replies  
**Schema**: `Comment` table with `parent_id` foreign key  
**Query**: Recursive query or Python tree building  
**Implementation**: `render_comment_tree()` builds tree structure  
**Date**: 2026-01-17

## API Patterns

### Pattern: Deployment Status Endpoint
**Route**: `/_deploy/status`  
**Method**: GET  
**Auth**: None (dev only)  
**Response**: JSON with deployment info, git commit, timestamp  
**Purpose**: Verify deployment, check what code is running  
**Date**: 2026-01-17

### Pattern: Deployment Reload Endpoint
**Route**: `/_deploy/reload`  
**Method**: POST  
**Auth**: None (dev only)  
**Response**: JSON with status  
**Purpose**: Clear cache and reload (dev only)  
**Date**: 2026-01-17

## Deployment Decisions

### Decision: Two-Branch Git Workflow
**Context**: Need to test changes before production  
**Alternatives**: Single branch, feature branches, GitFlow  
**Chosen**: `main` (prod) ← `dev` (dev) ← `feature/*` (temp)  
**Rationale**: Simple, clear separation, easy rollback  
**Date**: 2026-01-17

### Decision: Manual Database Migrations (for now)
**Context**: Need schema changes but no migration system  
**Alternatives**: Alembic, Flask-Migrate, manual SQL  
**Chosen**: Manual SQL + `db.create_all()` for new installs  
**Rationale**: Simple for now, plan to add Alembic later  
**Date**: 2026-01-17

### Decision: Python-based Deployment Scripts
**Context**: Need reliable, agent-friendly deployment  
**Alternatives**: Bash scripts, Makefile, CI/CD service  
**Chosen**: Python scripts (`deploy.py`, `verify.py`, etc.)  
**Rationale**: Better error handling, structured output, easier for agents  
**Date**: 2026-01-17

## Testing Patterns

### Pattern: HTTP Response Testing
**Use Case**: Verify service is responding  
**Implementation**: `requests.get(url)` check status code  
**Location**: `verify.py` (planned)

### Pattern: Content Verification
**Use Case**: Verify specific content appears  
**Implementation**: `response.text` contains expected string  
**Location**: `verify.py` (planned)

### Pattern: API Endpoint Testing
**Use Case**: Verify all routes work  
**Implementation**: Test each route, check response format  
**Location**: `tests/integration/test_api_routes.py` (planned)

## Current Work (2026-01-17)

**Feature**: Agent Deployment System  
**Status**: Implementation in progress  
**Branch**: `dev`  
**Components**: 
- `deploy.py` - Main deployment script
- `verify.py` - Verification script
- `status.py` - Status checking
- `rollback.py` - Rollback capability
- `tests/` - Test framework

**Next Steps**:
1. Implement `deploy.py` with full pipeline
2. Implement `verify.py` with comprehensive checks
3. Add test framework
4. Test in dev environment
5. Migrate to production when ready

## Important Notes

- **Production Safety**: Always backup before changes
- **Git Tags**: Tag production state before major changes
- **Environment**: Always check `FLASK_ENV` before operations
- **Cache**: Always clear Python cache on deployment
- **Service**: Always restart service after code changes
- **Verification**: Always verify after deployment

## References

- `SAFE_MIGRATION_PLAN.md` - Migration strategy
- `IMPLEMENTATION_ROADMAP.md` - Detailed implementation plan
- `AGENT_DEPLOYMENT_PLAN.md` - High-level architecture
- `JAUmemory_INTEGRATION.md` - How to use JAUmemory
