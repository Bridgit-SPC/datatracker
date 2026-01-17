#!/bin/bash
# Copy production database to development for testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Migrating Production Database to Development"
echo "=========================================="

if [ ! -f "instance/datatracker.db" ]; then
    echo "Error: Production database not found at instance/datatracker.db"
    exit 1
fi

# Stop dev service if running
if systemctl --user is-active --quiet datatracker-dev.service; then
    echo "Stopping development service..."
    systemctl --user stop datatracker-dev.service
fi

# Backup existing dev database
if [ -f "instance_dev/datatracker_dev.db" ]; then
    BACKUP="instance_dev/datatracker_dev.db.backup.$(date +%Y%m%d_%H%M%S)"
    cp "instance_dev/datatracker_dev.db" "$BACKUP"
    echo "✓ Backed up existing dev database to $BACKUP"
fi

# Copy production database
mkdir -p instance_dev
cp "instance/datatracker.db" "instance_dev/datatracker_dev.db"
echo "✓ Copied production database to development"

# Start dev service
echo "Starting development service..."
systemctl --user start datatracker-dev.service
sleep 2
systemctl --user status datatracker-dev.service --no-pager || true

echo ""
echo "=========================================="
echo "Migration complete!"
echo "Development database now matches production"
echo "=========================================="
