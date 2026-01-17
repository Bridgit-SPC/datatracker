#!/bin/bash
# Safe Migration Script - Prepares for new deployment system without breaking production

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "SAFE MIGRATION - Preparing New System"
echo "=========================================="
echo ""
echo "This script will:"
echo "1. Create backups of production"
echo "2. Create dev branch"
echo "3. Prepare for new deployment system"
echo "4. Keep production completely unchanged"
echo ""

# Check for --yes flag or AUTO_YES environment variable
AUTO_YES=false
if [[ "$1" == "--yes" ]] || [[ "$1" == "-y" ]] || [[ "${AUTO_YES:-false}" == "true" ]]; then
    AUTO_YES=true
fi

if [[ "$AUTO_YES" != "true" ]]; then
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 1
    fi
else
    echo "Auto-confirmed (--yes flag or AUTO_YES=true)"
fi

# Step 1: Create backups
echo ""
echo "Step 1: Creating backups..."
BACKUP_DIR="backups/safe-migration-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup database
if [ -f "instance/datatracker.db" ]; then
    cp "instance/datatracker.db" "$BACKUP_DIR/prod-database.db"
    echo "✓ Production database backed up"
fi

# Backup service files
if [ -f ~/.config/systemd/user/datatracker.service ]; then
    cp ~/.config/systemd/user/datatracker.service "$BACKUP_DIR/"
    echo "✓ Production service file backed up"
fi

if [ -f ~/.config/systemd/user/datatracker-dev.service ]; then
    cp ~/.config/systemd/user/datatracker-dev.service "$BACKUP_DIR/"
    echo "✓ Dev service file backed up"
fi

# Backup current code state
echo "Step 2: Tagging current production state..."
CURRENT_COMMIT=$(git rev-parse HEAD)
CURRENT_BRANCH=$(git branch --show-current)
TAG_NAME="production-stable-$(date +%Y%m%d)"

git tag "$TAG_NAME"
echo "✓ Tagged as: $TAG_NAME"
echo "  Commit: $CURRENT_COMMIT"
echo "  Branch: $CURRENT_BRANCH"

# Save state
cat > "$BACKUP_DIR/state.txt" <<EOF
Migration Date: $(date)
Current Commit: $CURRENT_COMMIT
Current Branch: $CURRENT_BRANCH
Tag: $TAG_NAME
EOF

# Step 3: Create dev branch (if doesn't exist)
echo ""
echo "Step 3: Creating dev branch..."
if git show-ref --verify --quiet refs/heads/dev; then
    echo "⚠ Dev branch already exists"
    if [[ "$AUTO_YES" == "true" ]]; then
        echo "Auto-recreating dev branch (--yes flag)"
        git branch -D dev
        git checkout -b dev
        echo "✓ Dev branch recreated"
    else
        read -p "Delete and recreate? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git branch -D dev
            git checkout -b dev
            echo "✓ Dev branch recreated"
        else
            echo "Keeping existing dev branch"
            git checkout dev
        fi
    fi
else
    git checkout -b dev
    echo "✓ Dev branch created"
fi

# Step 4: Switch back to main
echo ""
echo "Step 4: Switching back to main branch..."
git checkout main
echo "✓ Back on main branch (production unchanged)"

# Summary
echo ""
echo "=========================================="
echo "MIGRATION PREPARATION COMPLETE"
echo "=========================================="
echo ""
echo "Backups created in: $BACKUP_DIR"
echo "Production tagged as: $TAG_NAME"
echo "Dev branch created: dev"
echo ""
echo "Production is UNCHANGED and still running."
echo "You can now safely add new scripts to dev branch."
echo ""
echo "Next steps:"
echo "1. git checkout dev"
echo "2. Add new deployment scripts"
echo "3. Test in dev environment"
echo "4. When ready, merge dev to main"
echo ""
