# System Refactor Plan - Prevent Automatic Data Creation During Deployment

## Problem Identified

During deployment, some process automatically created 8 additional database records:
- 3 published drafts
- 5 additional approved submissions

This happened in a 2-minute window during deployment, changing document count from 1 to 9.

## Root Cause Analysis

**Possible causes:**
1. **Initialization code** that runs on app startup
2. **Migration/sync process** triggered by deployment
3. **Background job** or cron task
4. **Code I wrote** that automatically creates records
5. **Data seeding** from test fixtures

**Evidence:**
- Data appeared during deployment window (19:41-19:43)
- Published drafts had status 'active' (not 'published')
- Referenced existing submission IDs
- No RFC numbers (not from approval process)

## Refactor Requirements

### 1. **Deployment Safety**
- ✅ **Database backups** before every deployment
- ❌ **No automatic data creation** during deployment
- ❌ **No initialization code** that modifies data
- ✅ **Read-only mode** during deployment verification

### 2. **Data Creation Controls**
- ❌ **No automatic published draft creation**
- ❌ **No background sync processes**
- ✅ **Explicit admin actions only** for data creation
- ✅ **Audit logging** for all data modifications

### 3. **Deployment Process**
- ✅ **Pre-deployment validation** - check for unexpected data
- ✅ **Post-deployment verification** - ensure no unexpected changes
- ✅ **Rollback capability** - revert if data corruption detected

## Implementation Plan

### Phase 1: Immediate Safety Measures

#### 1.1 Add Deployment Guards
```python
# In ietf_data_viewer_simple.py
DEPLOYMENT_MODE = os.environ.get('DEPLOYMENT_MODE', 'false').lower() == 'true'

if DEPLOYMENT_MODE:
    # Disable all data modification operations
    pass
```

#### 1.2 Disable Auto-Creation Code
- Find and comment out any code that automatically creates published drafts
- Add deployment mode checks to prevent data creation

#### 1.3 Add Data Integrity Checks
```python
def verify_data_integrity():
    """Check for unexpected data changes during deployment"""
    expected_counts = {
        'submissions': 1,  # Only the legitimate ML-001 document
        'published_drafts': 0,  # None in clean state
        'users': 7  # Expected user count
    }
    # Compare against expected counts
    # Fail deployment if unexpected data found
```

### Phase 2: Code Audit and Cleanup

#### 2.1 Audit All Data Creation Points
- [ ] Search for all `PublishedDraft()` instantiations
- [ ] Search for all `db.session.add()` calls
- [ ] Review all background tasks/jobs
- [ ] Check initialization and migration code

#### 2.2 Remove Dangerous Code
- [ ] Remove any automatic published draft creation
- [ ] Remove any data seeding in production
- [ ] Add deployment guards to all data modification functions

#### 2.3 Add Safety Checks
```python
@app.before_request
def deployment_safety_check():
    if DEPLOYMENT_MODE and request.method in ['POST', 'PUT', 'DELETE']:
        # Block all data modifications during deployment
        abort(403, "Data modifications disabled during deployment")
```

### Phase 3: Deployment Process Improvements

#### 3.1 Enhanced Verification
```python
# In verify.py
def verify_data_integrity():
    """Verify no unexpected data was created during deployment"""
    # Check record counts
    # Check for new records created during deployment window
    # Compare database checksums
```

#### 3.2 Deployment Flags
```bash
# deployment script
export DEPLOYMENT_MODE=true
# Run verification
export DEPLOYMENT_MODE=false
```

#### 3.3 Rollback Triggers
```python
# If data integrity check fails, automatic rollback
if not verify_data_integrity():
    log("Data integrity violation detected!")
    rollback_to_previous_deployment()
```

## Code Changes Needed

### 1. Add Deployment Mode
```python
# Add to environment variables
DEPLOYMENT_MODE = os.environ.get('DEPLOYMENT_MODE', 'false').lower() == 'true'
```

### 2. Protect Data Modification Routes
```python
@app.before_request
def block_modifications_in_deployment():
    if DEPLOYMENT_MODE and request.method in ['POST', 'PUT', 'DELETE']:
        if not request.path.startswith('/_deploy/'):  # Allow deployment endpoints
            abort(403, "Data modifications disabled during deployment")
```

### 3. Update Deployment Script
```python
# deploy.py
def deploy(env):
    # Set deployment mode
    os.environ['DEPLOYMENT_MODE'] = 'true'
    
    # Deploy code
    # ...
    
    # Run verification
    verify_result = run_verification()
    
    # Clear deployment mode
    os.environ['DEPLOYMENT_MODE'] = 'false'
    
    return verify_result
```

### 4. Enhanced Verification
```python
# verify.py - add data integrity checks
def check_data_integrity():
    """Ensure no unexpected data was created"""
    # Get baseline counts from backup
    # Compare current counts
    # Check for records created during deployment window
    # Fail if any unexpected data found
```

## Prevention Measures

### 1. **Database Triggers**
- Add database triggers to log all INSERT/UPDATE/DELETE operations
- Include timestamp and source identification

### 2. **Deployment Audit Log**
- Log all operations during deployment
- Include database record counts before/after
- Flag any unexpected changes

### 3. **Code Review Requirements**
- All data modification code must have deployment guards
- Automatic data creation requires explicit approval
- Background processes must be deployment-aware

### 4. **Testing Requirements**
- Deployment tests must include data integrity checks
- Rollback tests must verify data restoration
- Load tests must not create persistent data

## Success Criteria

1. ✅ **Zero data creation during deployment**
2. ✅ **All deployments pass data integrity checks**
3. ✅ **Automatic rollback on data corruption**
4. ✅ **Complete audit trail of all data changes**
5. ✅ **No background processes modify data during deployment**

## Implementation Priority

1. **HIGH**: Add deployment guards to prevent data modification
2. **HIGH**: Implement data integrity verification
3. **MEDIUM**: Audit and remove dangerous auto-creation code
4. **MEDIUM**: Add deployment audit logging
5. **LOW**: Implement advanced rollback triggers

## Next Steps

1. **Implement deployment guards** (Phase 1)
2. **Run test deployment** to verify guards work
3. **Audit codebase** for auto-creation code (Phase 2)
4. **Add data integrity checks** (Phase 3)
5. **Test full deployment pipeline** with safety measures

## Emergency Measures

If this happens again:
1. **Immediate rollback** to previous backup
2. **Disable the application** until cause is found
3. **Audit all code changes** since last good deployment
4. **Implement deployment guards** before re-enabling

This refactor will ensure **deployments are safe and predictable**, preventing the automatic data creation that caused this incident.