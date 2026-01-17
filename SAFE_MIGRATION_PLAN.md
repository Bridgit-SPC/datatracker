# Safe Migration Plan - Deploy New System Without Breaking Production

## Goal
Deploy the new agent deployment system without disrupting the currently running production code.

## Current State
- Production: Running on `main` branch, port 8000, `rfc.themetalayer.org`
- Development: Running on `main` branch, port 8001, `dev.rfc.themetalayer.org`
- Both environments use same codebase, different databases

## Migration Strategy: Zero-Risk Approach

### Phase 1: Prepare (No Changes to Production)

**Step 1.1: Backup Everything**
```bash
# Backup production database
cp instance/datatracker.db backups/production-backup-$(date +%Y%m%d_%H%M%S).db

# Backup current code
git tag production-before-migration-$(date +%Y%m%d)
git push origin production-before-migration-$(date +%Y%m%d)

# Backup service files
cp ~/.config/systemd/user/datatracker.service ~/.config/systemd/user/datatracker.service.backup
cp ~/.config/systemd/user/datatracker-dev.service ~/.config/systemd/user/datatracker-dev.service.backup
```

**Step 1.2: Create Dev Branch (Doesn't Affect Production)**
```bash
# Create dev branch from current main
git checkout -b dev
git push origin dev

# Keep main as-is for production
git checkout main
```

**Step 1.3: Add New Scripts (Non-Breaking)**
```bash
# Add new deployment scripts
# These don't affect existing code, just add new files
git add deploy.py verify.py status.py rollback.py
git commit -m "Add new deployment system scripts"
git push origin dev
```

### Phase 2: Test New System in Dev Only

**Step 2.1: Update Dev Environment to Use New Scripts**
```bash
# Update dev service to use dev branch (doesn't affect prod)
# Modify datatracker-dev.service to checkout dev branch
# Test new deployment scripts in dev only
```

**Step 2.2: Verify Dev Works**
```bash
# Test new deployment system in dev
python3 deploy.py dev
python3 verify.py dev

# Ensure dev still works with new system
# Production still using old system, unaffected
```

### Phase 3: Migrate Production (When Ready)

**Step 3.1: Only After Dev Verified**
```bash
# Merge dev to main (when ready)
git checkout main
git merge dev
git push origin main

# Deploy to production using new system
python3 deploy.py prod
```

## Implementation: Non-Breaking Approach

### Option A: Parallel System (Safest)

**Keep old system working, add new system alongside:**

1. **New scripts don't replace old ones**
   - Old: `deploy.sh` (still works)
   - New: `deploy.py` (new system)
   - Both can coexist

2. **Gradual migration**
   - Start using new scripts in dev
   - Keep old scripts as backup
   - Switch production when confident

3. **Rollback plan**
   - If new system fails, use old scripts
   - Git tags allow easy rollback
   - Database backups allow data rollback

### Option B: Feature Flag Approach

**Add feature flag to enable/disable new system:**

```python
# In ietf_data_viewer_simple.py
USE_NEW_DEPLOYMENT_SYSTEM = os.environ.get('USE_NEW_DEPLOYMENT', 'false').lower() == 'true'

# New endpoints only active if flag set
if USE_NEW_DEPLOYMENT_SYSTEM:
    @app.route('/_deploy/status')
    def deployment_status():
        # New code
```

**Migration**:
1. Deploy code with flag (disabled) - no change in behavior
2. Enable flag in dev - test new system
3. Enable flag in prod - when ready

## Step-by-Step Safe Implementation

### Step 1: Create Backup and Safety Net

```bash
# 1. Tag current production state
cd /home/ubuntu/datatracker
git tag production-stable-$(date +%Y%m%d)
git push origin production-stable-$(date +%Y%m%d)

# 2. Backup production database
mkdir -p backups/safe-migration
cp instance/datatracker.db backups/safe-migration/prod-$(date +%Y%m%d_%H%M%S).db

# 3. Backup service files
cp ~/.config/systemd/user/datatracker.service backups/safe-migration/
cp ~/.config/systemd/user/datatracker-dev.service backups/safe-migration/

# 4. Document current state
echo "Production commit: $(git rev-parse HEAD)" > backups/safe-migration/state.txt
echo "Production branch: $(git branch --show-current)" >> backups/safe-migration/state.txt
```

### Step 2: Create Dev Branch (Doesn't Touch Production)

```bash
# Create dev branch from current main
git checkout -b dev
git push origin dev

# Switch back to main (production stays on main)
git checkout main
```

### Step 3: Add New Scripts to Dev Branch Only

```bash
# Switch to dev branch
git checkout dev

# Add new scripts (these are new files, don't modify existing code)
# Create: deploy.py, verify.py, status.py, rollback.py
# These are additions, not replacements

# Commit and push
git add deploy.py verify.py status.py rollback.py
git commit -m "Add new deployment system (dev branch only)"
git push origin dev

# Production (main branch) unchanged - still works
```

### Step 4: Test New System in Dev

```bash
# Update dev service to use dev branch (optional, can test manually first)
# Or just test scripts manually in dev environment

# Test new deployment
python3 deploy.py dev

# Verify it works
python3 verify.py dev

# Production still using old system - unaffected
```

### Step 5: Migrate Production (Only When Ready)

```bash
# Only after dev fully tested and verified

# Merge dev to main
git checkout main
git merge dev
git push origin main

# Deploy using new system
python3 deploy.py prod

# Old scripts still available as backup
```

## Safety Measures

### 1. Git Safety
- Tag production before any changes
- Keep old scripts as backup
- Can always checkout old commit

### 2. Database Safety
- Backup before any migration
- Test migrations in dev first
- Can restore from backup if needed

### 3. Service Safety
- Keep old service files as backup
- Can revert service config if needed
- Test in dev before prod

### 4. Code Safety
- New scripts are additions, not replacements
- Old code unchanged
- Feature flags for new functionality

## Rollback Plan

If anything goes wrong:

```bash
# 1. Revert code
git checkout production-stable-YYYYMMDD
git push origin main --force  # Only if necessary

# 2. Restore database
cp backups/safe-migration/prod-YYYYMMDD_HHMMSS.db instance/datatracker.db

# 3. Restore service files
cp backups/safe-migration/datatracker.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user restart datatracker.service

# 4. Verify production working
curl https://rfc.themetalayer.org/
```

## Implementation Order

1. **Week 1: Preparation**
   - Create backups
   - Create dev branch
   - Add new scripts to dev branch
   - Test scripts manually

2. **Week 2: Dev Testing**
   - Use new scripts in dev environment
   - Verify everything works
   - Fix any issues

3. **Week 3: Production Migration**
   - Merge dev to main
   - Deploy using new system
   - Monitor closely

4. **Week 4: Cleanup**
   - Remove old scripts (if desired)
   - Update documentation
   - Archive backups

## Key Principles

1. **Never modify production code directly**
2. **Always test in dev first**
3. **Keep backups of everything**
4. **Can rollback at any time**
5. **New system is additive, not replacement**
6. **Old system still works during migration**

## What Gets Changed

### Safe Changes (No Risk)
- ✅ Add new files (deploy.py, verify.py, etc.)
- ✅ Create dev branch
- ✅ Add new endpoints (with feature flag)
- ✅ Add new documentation

### Risky Changes (Do Later)
- ⚠️ Modify existing deployment scripts (keep old ones)
- ⚠️ Change service files (keep backups)
- ⚠️ Modify production code (test in dev first)

## Verification Checklist

Before migrating production:

- [ ] Backups created and verified
- [ ] Git tags created
- [ ] Dev branch created and tested
- [ ] New scripts work in dev
- [ ] Dev environment stable with new system
- [ ] Rollback plan tested
- [ ] Production still working (unchanged)
- [ ] Ready to merge dev to main

## Next Steps

1. **Review this plan**
2. **Create backups** (Step 1)
3. **Create dev branch** (Step 2)
4. **Add new scripts** (Step 3)
5. **Test in dev** (Step 4)
6. **Migrate production** (Step 5) - only when ready
