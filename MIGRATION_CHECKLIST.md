# Safe Migration Checklist

## Pre-Migration (Do Now - Zero Risk)

- [ ] **Review migration plan**: Read `SAFE_MIGRATION_PLAN.md`
- [ ] **Create backups**: Run `./safe-migration.sh`
- [ ] **Verify backups**: Check files in `backups/safe-migration-*/`
- [ ] **Verify production working**: Check https://rfc.themetalayer.org
- [ ] **Document current state**: Note any custom configurations

## Phase 1: Preparation (No Production Changes)

- [ ] **Create dev branch**: `git checkout -b dev` (from main)
- [ ] **Push dev branch**: `git push origin dev`
- [ ] **Switch back to main**: `git checkout main`
- [ ] **Verify production still on main**: `git branch --show-current`
- [ ] **Tag production**: `git tag production-stable-YYYYMMDD`

## Phase 2: Add New Scripts (Dev Branch Only)

- [ ] **Switch to dev**: `git checkout dev`
- [ ] **Add deploy.py**: New file, doesn't modify existing code
- [ ] **Add verify.py**: New file
- [ ] **Add status.py**: New file
- [ ] **Add rollback.py**: New file
- [ ] **Commit to dev**: `git commit -m "Add new deployment system"`
- [ ] **Push dev**: `git push origin dev`
- [ ] **Switch back to main**: `git checkout main`
- [ ] **Verify production unchanged**: Production still works

## Phase 3: Test in Dev (No Production Impact)

- [ ] **Test deploy.py in dev**: `python3 deploy.py dev`
- [ ] **Test verify.py in dev**: `python3 verify.py dev`
- [ ] **Verify dev environment works**: Check https://dev.rfc.themetalayer.org
- [ ] **Fix any issues**: In dev branch only
- [ ] **Re-test**: Until everything works in dev

## Phase 4: Production Migration (Only When Ready)

- [ ] **Final backup**: Create one more backup before migration
- [ ] **Verify dev stable**: Dev has been stable for X days
- [ ] **Merge dev to main**: `git checkout main && git merge dev`
- [ ] **Deploy to production**: `python3 deploy.py prod`
- [ ] **Verify production**: Check https://rfc.themetalayer.org
- [ ] **Monitor closely**: Watch for any issues

## Rollback Plan (If Needed)

- [ ] **Know rollback steps**: Review `SAFE_MIGRATION_PLAN.md` rollback section
- [ ] **Test rollback**: Practice rollback in dev first
- [ ] **Have backups ready**: Know where backups are
- [ ] **Have git tags ready**: Know which tag to revert to

## Post-Migration

- [ ] **Verify production stable**: Monitor for 24-48 hours
- [ ] **Update documentation**: Document new workflow
- [ ] **Archive old scripts**: Keep as backup, don't delete yet
- [ ] **Train on new system**: Understand new workflow
- [ ] **Clean up**: Remove old scripts after confidence period

## Safety Rules

1. ✅ **Never modify production code directly**
2. ✅ **Always test in dev first**
3. ✅ **Keep backups of everything**
4. ✅ **Can rollback at any time**
5. ✅ **New system is additive, not replacement**
6. ✅ **Old system still works during migration**

## Verification Commands

```bash
# Check current branch
git branch --show-current

# Check production status
systemctl --user status datatracker.service

# Check dev status  
systemctl --user status datatracker-dev.service

# Verify production URL
curl -I https://rfc.themetalayer.org

# Verify dev URL
curl -I https://dev.rfc.themetalayer.org

# Check backups
ls -lh backups/safe-migration-*/

# Check git tags
git tag | grep production-stable
```
