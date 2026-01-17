# Development Workflow - Daily Practices

## Quick Reference

### Starting a New Feature

1. **Query JAUmemory** for similar implementations
2. **Create feature branch**: `git checkout -b feature/feature-name`
3. **Make changes** and commit
4. **Deploy to dev**: `python3 deploy.py dev`
5. **Verify**: `python3 verify.py dev`
6. **If passes**: `python3 deploy.py prod`
7. **Store in JAUmemory**: Document what was done

### Making a Quick Fix

1. **Create fix branch**: `git checkout -b fix/issue-description`
2. **Make fix** and commit
3. **Deploy to dev**: `python3 deploy.py dev`
4. **Verify**: `python3 verify.py dev`
5. **If passes**: `python3 deploy.py prod`

### Database Changes

1. **Create migration file** in `migrations/`
2. **Test in dev**: `python3 deploy.py dev`
3. **Verify database**: `python3 verify.py dev`
4. **If passes**: `python3 deploy.py prod`

## Detailed Workflow

### Phase 1: Planning

1. **Understand Requirements**
   - Read feature request carefully
   - Identify affected components
   - Plan implementation approach

2. **Query JAUmemory**
   - "How was [similar feature] implemented?"
   - "What patterns are used for [component type]?"
   - "What issues were encountered with [related feature]?"

3. **Plan Implementation**
   - List files to modify
   - List tests to write
   - List migrations needed (if any)

### Phase 2: Implementation

1. **Create Branch**
   ```bash
   git checkout -b feature/feature-name
   ```

2. **Make Changes**
   - Follow existing code patterns
   - Add comments for complex logic
   - Keep commits focused and atomic

3. **Write Tests** (if needed)
   - Unit tests for functions
   - Integration tests for API routes
   - E2E tests for user flows

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "Description of changes"
   ```

### Phase 3: Development Deployment

1. **Deploy to Dev**
   ```bash
   python3 deploy.py dev
   ```
   - Automatically merges branch to `dev`
   - Deploys to dev environment
   - Runs basic health checks

2. **Verify Deployment**
   ```bash
   python3 verify.py dev
   ```
   - Tests all API routes
   - Verifies database state
   - Checks content changes
   - Runs regression tests

3. **If Verification Fails**
   - Review error output
   - Fix issues in feature branch
   - Re-deploy and re-verify
   - Do NOT proceed until verification passes

### Phase 4: Production Promotion

1. **Only if dev verification passed**
   ```bash
   python3 deploy.py prod
   ```
   - Merges `dev` to `main`
   - Creates backup
   - Deploys to production
   - Runs production verification

2. **Verify Production**
   ```bash
   python3 verify.py prod
   ```
   - Same verification as dev
   - Ensures production is working

3. **If Production Fails**
   - Rollback immediately: `python3 rollback.py prod`
   - Fix issues in dev
   - Re-deploy to dev
   - Re-verify
   - Try production again

### Phase 5: Documentation

1. **Store in JAUmemory**
   - Feature description
   - Implementation approach
   - Patterns used
   - Lessons learned
   - Issues encountered

2. **Update Documentation** (if needed)
   - Update `DEVELOPMENT_WORKFLOW.md` if process changed
   - Update `CODE_STANDARDS.md` if patterns changed
   - Update API docs if routes changed

## Common Tasks

### Adding a New API Route

1. Add route to `ietf_data_viewer_simple.py`
2. Add test to `tests/integration/test_api_routes.py`
3. Deploy to dev: `python3 deploy.py dev`
4. Verify: `python3 verify.py dev`
5. If passes: `python3 deploy.py prod`

### Changing Database Schema

1. Create migration in `migrations/001_description.py`
2. Test migration: `python3 deploy.py dev`
3. Verify database: `python3 verify.py dev`
4. If passes: `python3 deploy.py prod`

### Changing UI Content

1. Update template/content
2. Add content verification test
3. Deploy to dev: `python3 deploy.py dev`
4. Verify content: `python3 verify.py dev`
5. If passes: `python3 deploy.py prod`

### Fixing a Bug

1. Create fix branch: `git checkout -b fix/bug-description`
2. Fix the bug
3. Add test to prevent regression
4. Deploy to dev: `python3 deploy.py dev`
5. Verify fix: `python3 verify.py dev`
6. If passes: `python3 deploy.py prod`

## Verification Checklist

Before promoting to production, verify:

- [ ] Code deployed to dev successfully
- [ ] Service is running and healthy
- [ ] All API routes respond correctly
- [ ] Database schema is correct
- [ ] Expected content appears
- [ ] No regressions detected
- [ ] Tests pass
- [ ] Documentation updated (if needed)
- [ ] JAUmemory updated

## Error Handling

### If Deployment Fails

1. Check logs: `/var/log/datatracker/deployments.log`
2. Check service: `systemctl --user status datatracker-dev.service`
3. Fix issues in feature branch
4. Re-deploy
5. Document issue in JAUmemory

### If Verification Fails

1. Review verification output
2. Identify what failed
3. Fix in feature branch
4. Re-deploy and re-verify
5. Do NOT promote until fixed

### If Production Deployment Fails

1. Rollback immediately: `python3 rollback.py prod`
2. Verify rollback succeeded
3. Fix issues in dev
4. Re-test in dev
5. Try production again

## Best Practices

1. **Always deploy to dev first**
2. **Always verify before promoting**
3. **Never skip verification steps**
4. **Document decisions in JAUmemory**
5. **Test database migrations in dev**
6. **Keep commits focused and atomic**
7. **Write tests for new features**
8. **Check for regressions**
9. **Follow the workflow strictly**
10. **Query JAUmemory before starting**

## Staying On Track

**Reference Documents**:
- `AGENT_DEPLOYMENT_PLAN.md` - Overall architecture
- `IMPLEMENTATION_ROADMAP.md` - Implementation details
- `DEVELOPMENT_WORKFLOW.md` - This document
- `CODE_STANDARDS.md` - Coding conventions
- `TESTING_GUIDE.md` - Testing practices
- `DATABASE_MIGRATIONS.md` - Migration process

**JAUmemory Queries**:
- Before starting: Query for similar work
- During development: Store decisions
- After completion: Document learnings

**Checkpoints**:
- Before each deployment: Am I following the workflow?
- Before production: Has dev verification passed?
- After completion: Is everything documented?
