#!/bin/bash
# Setup development environment for MLTF Datatracker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Setting up MLTF Datatracker Development Environment"
echo "=========================================="

# Create development instance directory
mkdir -p instance_dev
echo "✓ Created instance_dev directory"

# Copy production database to dev for testing (optional)
if [ -f "instance/datatracker.db" ]; then
    read -p "Copy production database to dev? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp "instance/datatracker.db" "instance_dev/datatracker_dev.db"
        echo "✓ Copied production database to dev"
    fi
fi

# Create systemd service file for dev
SERVICE_FILE="$HOME/.config/systemd/user/datatracker-dev.service"
mkdir -p "$(dirname "$SERVICE_FILE")"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=MLTF Datatracker Flask Application (Development)
After=network.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
Environment=FLASK_ENV=development
Environment=FLASK_PORT=8001
ExecStart=/home/ubuntu/.pyenv/versions/3.9.18/bin/python3 $SCRIPT_DIR/ietf_data_viewer_simple.py
Restart=always
RestartSec=5
Environment=PATH=/home/ubuntu/.pyenv/versions/3.9.18/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

echo "✓ Created systemd service file: $SERVICE_FILE"

# Reload systemd
systemctl --user daemon-reload
echo "✓ Reloaded systemd daemon"

# Enable and start dev service
systemctl --user enable datatracker-dev.service
systemctl --user start datatracker-dev.service
echo "✓ Started development service"

echo ""
echo "=========================================="
echo "Development environment setup complete!"
echo ""
echo "Development server: http://localhost:8001"
echo "Production server: http://rfc.themetalayer.org"
echo ""
echo "To manage services:"
echo "  Production: systemctl --user {start|stop|restart|status} datatracker.service"
echo "  Development: systemctl --user {start|stop|restart|status} datatracker-dev.service"
echo "=========================================="
