# Backup File Locations

## Current Backups

Backups created during migration preparation are stored in:

```
backups/safe-migration-YYYYMMDD_HHMMSS/
```

### Backup Contents

Each backup directory contains:
- `prod-database.db` - Production database snapshot
- `datatracker.service` - Production systemd service file
- `datatracker-dev.service` - Development systemd service file  
- `state.txt` - Migration state information (commit, branch, tag)

### Git Tags

Production state is also tagged in git:
- Tag format: `production-stable-YYYYMMDD`
- These tags allow you to checkout the exact production state

## When to Remove Backups

**DO NOT DELETE BACKUPS UNTIL:**
1. ✅ New deployment system is fully tested in dev
2. ✅ Production migration is complete and successful
3. ✅ System has been stable for at least 1 week
4. ✅ You are CERTAIN no rollback is needed

## How to Remove Backups

**When ready, use the cleanup script:**

```bash
./cleanup-backups.sh --confirm
```

This script:
- Requires explicit `--confirm` flag
- Requires typing "DELETE ALL BACKUPS" exactly
- Requires final "yes" confirmation
- Lists all files before deletion
- Safely removes all backup files

## Safety Notes

- **Backups are your safety net** - Keep them until you're 100% confident
- **Git tags remain** - Even after cleanup, git tags provide rollback capability
- **Remote backups** - Consider keeping one backup off-server for extra safety
- **Database backups** - Production database backups are separate from migration backups

## Current Backup Status

Run this to see current backups:

```bash
ls -lh backups/safe-migration-*/
```

To see backup details:

```bash
cat backups/safe-migration-*/state.txt
```
