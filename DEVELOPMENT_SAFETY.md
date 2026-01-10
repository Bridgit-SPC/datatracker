# MLTF Datatracker - Safe Development Practices

## 🎯 Preventing Feature Regressions

This document outlines practices to prevent accidentally breaking working functionality during development.

## 🧪 Automated Testing Framework

### Pre-commit Hook
- **Location**: `.git/hooks/pre-commit`
- **Purpose**: Runs automatically before every commit
- **Blocks commits** if critical features are broken
- **Override**: Use `git commit --no-verify` for emergencies only

### Core Feature Tests
- **File**: `test_core_features.py`
- **Tests**:
  - ✅ Authentication system
  - ✅ Admin dashboard access
  - ✅ User management functionality
  - ✅ Document system (listing, individual pages)
  - ✅ Comment system (submission, display, likes)
  - ✅ Submission workflow
  - ✅ Working groups
  - ✅ Chair management
  - ✅ Theme system

### Manual Verification
```bash
# Quick verification
python3 test_core_features.py

# Development workflow (with backup)
./dev_workflow.sh

# Just verify changes
./dev_workflow.sh --verify
```

## 🔧 Development Workflow

### For Major Changes (Recommended)

1. **Start Safe Workflow**:
   ```bash
   ./dev_workflow.sh
   ```
   This creates a backup and verifies everything works.

2. **Make Changes**:
   Edit files as needed.

3. **Verify Changes**:
   ```bash
   ./dev_workflow.sh --verify
   ```

4. **Commit if Safe**:
   ```bash
   git add .
   git commit -m "Your message"
   ```

### For Quick Changes

1. **Quick Verify**:
   ```bash
   python3 test_core_features.py
   ```

2. **Make Changes**

3. **Verify Again**:
   ```bash
   python3 test_core_features.py
   ```

## 📋 Best Practices

### Before Making Changes
- [ ] Run `python3 test_core_features.py`
- [ ] Check what features currently work
- [ ] Note any existing functionality you might affect

### During Changes
- [ ] Work on one feature at a time
- [ ] Test related functionality frequently
- [ ] Use `git stash` to save work if needed

### Before Committing
- [ ] Run full test suite: `python3 test_core_features.py`
- [ ] Verify critical user journeys work
- [ ] Check that existing features weren't broken

## 🚨 Emergency Recovery

### If Tests Fail After Changes
```bash
# See what changed
git diff

# Restore from backup (if using dev_workflow.sh)
tar -xzf backup_YYYYMMDD_HHMMSS.tar.gz

# Or revert specific commits
git log --oneline -10  # Find the commit
git revert <commit-hash>
```

### If You Must Commit Broken Code
```bash
# Only for true emergencies
git commit --no-verify -m "EMERGENCY: Broken commit - fix immediately"
```

## 🔍 What Gets Tested

### Critical User Journeys
1. **User Registration/Login** → Dashboard access
2. **Document Browsing** → View drafts, comments, history
3. **Comment System** → Post, like, reply to comments
4. **Admin Functions** → User management, submissions, analytics
5. **Theme System** → Dark/light mode switching
6. **Working Groups** → Chair management, membership

### Database Integrity
- User accounts and roles
- Draft submissions and status
- Comments and relationships
- Working group chairs
- Document history

## 🎯 Prevention Philosophy

**"Test First, Commit Safely"**

- Always verify before major changes
- Never commit without testing
- Have recovery plans ready
- Document what you break (and fix it!)

## 📞 Need Help?

If you break something:
1. Don't panic - we have backups and git history
2. Run the tests to see what's broken
3. Fix or revert the changes
4. Test again before committing

**Remember**: It's better to take longer and do it right than to break working features! 🛡️