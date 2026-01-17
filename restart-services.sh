#!/bin/bash
# Reliable service restart script

set -e

ENV="${1:-both}"

echo "=========================================="
echo "Restarting MLTF Datatracker Services"
echo "=========================================="

if [ "$ENV" == "production" ] || [ "$ENV" == "both" ]; then
    echo "Stopping production service..."
    systemctl --user stop datatracker.service || true
    sleep 2
    echo "Starting production service..."
    systemctl --user start datatracker.service
    sleep 3
    if systemctl --user is-active --quiet datatracker.service; then
        echo "✓ Production service is running"
    else
        echo "✗ Production service failed to start"
        systemctl --user status datatracker.service --no-pager | head -10
    fi
fi

if [ "$ENV" == "development" ] || [ "$ENV" == "both" ]; then
    echo "Stopping development service..."
    systemctl --user stop datatracker-dev.service || true
    sleep 2
    echo "Starting development service..."
    systemctl --user start datatracker-dev.service
    sleep 3
    if systemctl --user is-active --quiet datatracker-dev.service; then
        echo "✓ Development service is running"
    else
        echo "✗ Development service failed to start"
        systemctl --user status datatracker-dev.service --no-pager | head -10
    fi
fi

echo ""
echo "=========================================="
echo "Service restart complete"
echo "=========================================="
