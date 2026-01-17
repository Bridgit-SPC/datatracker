#!/bin/bash
# Cleanup Backup Files - REMOVES ALL BACKUPS
# 
# WARNING: This script permanently deletes backup files.
# Only run this AFTER verifying the new system is working correctly.
# 
# Usage: ./cleanup-backups.sh --confirm

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "BACKUP CLEANUP - REMOVES ALL BACKUPS"
echo "=========================================="
echo ""
echo "⚠️  WARNING: This will permanently delete:"
echo "   - All files in backups/safe-migration-*/"
echo "   - All backup database files"
echo "   - All backup service files"
echo ""
echo "This should ONLY be run after:"
echo "  1. New deployment system is fully tested"
echo "  2. Production migration is complete"
echo "  3. System has been stable for at least 1 week"
echo "  4. You are CERTAIN no rollback is needed"
echo ""

# Require explicit confirmation
if [[ "$1" != "--confirm" ]]; then
    echo "❌ SAFETY CHECK FAILED"
    echo ""
    echo "This script requires explicit --confirm flag."
    echo "Usage: ./cleanup-backups.sh --confirm"
    echo ""
    echo "If you're sure, run: ./cleanup-backups.sh --confirm"
    exit 1
fi

# Double-check
echo "Are you ABSOLUTELY SURE you want to delete all backups?"
echo "Type 'DELETE ALL BACKUPS' (exactly) to confirm: "
read -r CONFIRM_TEXT

if [[ "$CONFIRM_TEXT" != "DELETE ALL BACKUPS" ]]; then
    echo "❌ Confirmation text did not match. Aborting."
    exit 1
fi

# List what will be deleted
echo ""
echo "Files to be deleted:"
echo "===================="

BACKUP_COUNT=0
if [ -d "backups" ]; then
    find backups -type f -name "*.db" -o -name "*.service" -o -name "state.txt" | while read -r file; do
        echo "  $file"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    done
    
    # Count backup directories
    BACKUP_DIRS=$(find backups -type d -name "safe-migration-*" 2>/dev/null | wc -l)
    echo ""
    echo "Backup directories: $BACKUP_DIRS"
    echo "Backup files: $BACKUP_COUNT"
fi

echo ""
read -p "Proceed with deletion? (yes/no): " -r FINAL_CONFIRM
if [[ ! $FINAL_CONFIRM =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "❌ Aborted."
    exit 1
fi

# Delete backups
echo ""
echo "Deleting backups..."
if [ -d "backups" ]; then
    # Delete all safe-migration directories
    find backups -type d -name "safe-migration-*" -exec rm -rf {} + 2>/dev/null || true
    
    # Delete any remaining backup files
    find backups -type f \( -name "*.db" -o -name "*.service" -o -name "state.txt" \) -delete 2>/dev/null || true
    
    echo "✓ Backup directories deleted"
    echo "✓ Backup files deleted"
    
    # Remove backups directory if empty
    if [ -z "$(ls -A backups 2>/dev/null)" ]; then
        rmdir backups 2>/dev/null || true
        echo "✓ Empty backups directory removed"
    fi
else
    echo "⚠ No backups directory found"
fi

# Also remove git tags (optional - commented out for safety)
# Uncomment if you want to remove production-stable tags too
# echo ""
# echo "Remove production-stable git tags? (y/N): "
# read -r REMOVE_TAGS
# if [[ $REMOVE_TAGS =~ ^[Yy]$ ]]; then
#     git tag -l "production-stable-*" | xargs git tag -d 2>/dev/null || true
#     echo "✓ Git tags removed (local only)"
#     echo "  Note: Remote tags still exist. Remove with: git push origin --delete <tag>"
# fi

echo ""
echo "=========================================="
echo "CLEANUP COMPLETE"
echo "=========================================="
echo ""
echo "✓ All backup files have been deleted"
echo ""
echo "Note: Git tags remain for reference."
echo "      To remove tags: git tag -d production-stable-*"
echo ""
