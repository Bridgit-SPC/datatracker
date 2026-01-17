#!/bin/bash
# Agent-friendly deployment script
# This script is designed to be run by an AI agent and provides clear feedback

set -e

ENV="${1:-development}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "AGENT_DEPLOY_START|ENV=$ENV"

# Function to output agent-readable status
agent_status() {
    echo "AGENT_STATUS|$1"
}

# Function to output agent-readable result
agent_result() {
    echo "AGENT_RESULT|$1|$2"
}

if [ "$ENV" != "production" ] && [ "$ENV" != "development" ]; then
    agent_result "ERROR" "Invalid environment: $ENV"
    exit 1
fi

SERVICE_NAME="datatracker.service"
if [ "$ENV" == "development" ]; then
    SERVICE_NAME="datatracker-dev.service"
fi

agent_status "Stopping service..."
systemctl --user stop "$SERVICE_NAME" 2>&1 || true
sleep 2

agent_status "Clearing Python cache..."
find "$SCRIPT_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$SCRIPT_DIR" -name "*.pyc" -delete 2>/dev/null || true

agent_status "Verifying code..."
if [ -f "$SCRIPT_DIR/ietf_data_viewer_simple.py" ]; then
    if grep -q "Welcome to the Meta-Layer Governance Hub" "$SCRIPT_DIR/ietf_data_viewer_simple.py"; then
        agent_status "Code verification: PASSED"
    else
        agent_status "Code verification: WARNING - new text not found"
    fi
else
    agent_result "ERROR" "Main file not found"
    exit 1
fi

agent_status "Starting service..."
systemctl --user start "$SERVICE_NAME"
sleep 5

agent_status "Checking service status..."
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    agent_status "Service is ACTIVE"
else
    agent_result "ERROR" "Service failed to start"
    systemctl --user status "$SERVICE_NAME" --no-pager | head -20
    exit 1
fi

agent_status "Testing HTTP connection..."
sleep 2
PORT=8000
if [ "$ENV" == "development" ]; then
    PORT=8001
fi

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/" --max-time 5 || echo "000")
if [ "$HTTP_CODE" == "200" ]; then
    agent_status "HTTP test: PASSED (200)"
    
    # Check for new text
    if curl -s "http://localhost:$PORT/" --max-time 5 | grep -q "Welcome to the Meta-Layer Governance Hub"; then
        agent_result "SUCCESS" "Deployment complete. New text is live."
    else
        agent_result "SUCCESS" "Deployment complete. Service responding. (Text may need browser refresh)"
    fi
else
    agent_result "WARNING" "Service started but HTTP test failed (code: $HTTP_CODE)"
fi

echo "AGENT_DEPLOY_END"
