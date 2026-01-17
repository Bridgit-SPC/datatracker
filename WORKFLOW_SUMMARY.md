# Development Workflow Summary

## Current Setup

✅ **Single Codebase, Two Environments**
- Production: `rfc.themetalayer.org` (port 8000, database: `instance/datatracker.db`)
- Development: `dev.rfc.themetalayer.org` (port 8001, database: `instance_dev/datatracker_dev.db`)
- Both use the **same code** from `main` branch
- Environment controlled by `FLASK_ENV` variable

## Recommended Workflow: Single Branch (Main)

Since you have separate environments, you can use a **single branch** approach:

### Daily Workflow

1. **Make changes** to code
2. **Test in development**:
   ```bash
   ./deploy.sh development
   # Visit https://dev.rfc.themetalayer.org
   ```
3. **If tests pass, deploy to production**:
   ```bash
   ./deploy.sh production
   # Live at https://rfc.themetalayer.org
   ```

### Git Workflow

```bash
# Make changes
git add .
git commit -m "Description of changes"

# Test in dev
./deploy.sh development

# If good, deploy to prod
./deploy.sh production

# Push to remote (optional)
git push
```

## Alternative: Dev Branch (If You Want Separation)

If you prefer separate branches:

```bash
# Create dev branch
git checkout -b dev

# Make changes on dev
git add .
git commit -m "New feature"

# Deploy dev branch to dev environment
git checkout dev
./deploy.sh development

# When ready, merge to main
git checkout main
git merge dev
./deploy.sh production
```

## Key Points

- ✅ **Same codebase** - no need to maintain two codebases
- ✅ **Separate databases** - dev and prod data are isolated
- ✅ **Environment variables** - `FLASK_ENV` controls behavior
- ✅ **Automatic backups** - production DB backed up before each deploy
- ✅ **Zero downtime** - services restart seamlessly

## Quick Commands

```bash
# Deploy
./deploy.sh development    # Deploy to dev
./deploy.sh production     # Deploy to prod

# Services
systemctl --user restart datatracker.service        # Production
systemctl --user restart datatracker-dev.service     # Development

# Database
./migrate-to-dev.sh       # Copy prod data to dev for testing
```

## Recommendation

**Use single `main` branch** - it's simpler and your environment separation already handles isolation. You can always add branches later if the team grows or workflow becomes more complex.
