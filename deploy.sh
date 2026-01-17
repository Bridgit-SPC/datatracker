#!/bin/bash
# Zero-downtime deployment script for MLTF Datatracker

set -e

ENV="${1:-production}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ "$ENV" != "production" ] && [ "$ENV" != "development" ]; then
    echo "Usage: $0 [production|development]"
    exit 1
fi

echo "=========================================="
echo "MLTF Datatracker Deployment"
echo "Environment: $ENV"
echo "=========================================="

# Backup production database before deployment
if [ "$ENV" == "production" ]; then
    echo "Creating database backup..."
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    if [ -f "instance/datatracker.db" ]; then
        cp "instance/datatracker.db" "$BACKUP_DIR/datatracker.db"
        echo "✓ Database backed up to $BACKUP_DIR/"
    fi
fi

# Pull latest code (if using git)
if [ -d ".git" ]; then
    echo "Pulling latest code..."
    # Check if we're on a branch that tracks remote
    CURRENT_BRANCH=$(git branch --show-current)
    if [ -n "$CURRENT_BRANCH" ] && git rev-parse --abbrev-ref --symbolic-full-name "$CURRENT_BRANCH@{u}" >/dev/null 2>&1; then
        git pull || echo "Warning: git pull failed, continuing with current code"
    else
        echo "No remote tracking branch, skipping git pull"
    fi
fi

# Install/update dependencies
if [ -f "requirements.txt" ]; then
    echo "Checking dependencies..."
    pip3 install -q -r requirements.txt || echo "Warning: Some dependencies may have failed to install"
fi

# Run database migrations if needed
echo "Initializing database..."
FLASK_ENV="$ENV" python3 -c "
from ietf_data_viewer_simple import init_db, app
with app.app_context():
    init_db()
print('✓ Database initialized')
"

# Use agent deployment script for reliable deployment
echo "Deploying using agent deployment system..."
if [ -f "$SCRIPT_DIR/agent-deploy.sh" ]; then
    "$SCRIPT_DIR/agent-deploy.sh" "$ENV"
    DEPLOY_EXIT=$?
    if [ $DEPLOY_EXIT -eq 0 ]; then
        echo "✓ Deployment successful"
    else
        echo "✗ Deployment failed"
        exit 1
    fi
else
    # Fallback to manual restart if agent script doesn't exist
    echo "Agent deployment script not found, using manual restart..."
    if [ "$ENV" == "production" ]; then
        systemctl --user stop datatracker.service || true
        sleep 2
        systemctl --user start datatracker.service
        sleep 3
        if ! systemctl --user is-active --quiet datatracker.service; then
            systemctl --user status datatracker.service --no-pager | head -10
            exit 1
        fi
    else
        systemctl --user stop datatracker-dev.service || true
        sleep 2
        systemctl --user start datatracker-dev.service
        sleep 3
        if ! systemctl --user is-active --quiet datatracker-dev.service; then
            systemctl --user status datatracker-dev.service --no-pager | head -10
            exit 1
        fi
    fi
fi

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "Environment: $ENV"
echo "=========================================="
