#!/bin/bash

# MLTF Datatracker Service Management Script

SERVICE_NAME="datatracker.service"

# Function to reload systemd daemon if needed
reload_daemon_if_needed() {
    if systemctl --user show $SERVICE_NAME 2>/dev/null | grep -q "NeedDaemonReload=yes"; then
        echo "Reloading systemd user daemon..."
        systemctl --user daemon-reload
    fi
}

case "$1" in
    start)
        echo "Starting datatracker service..."
        reload_daemon_if_needed
        systemctl --user start $SERVICE_NAME
        ;;
    stop)
        echo "Stopping datatracker service..."
        systemctl --user stop $SERVICE_NAME
        ;;
    restart)
        echo "Restarting datatracker service..."
        reload_daemon_if_needed
        systemctl --user restart $SERVICE_NAME
        ;;
    status)
        echo "Datatracker service status:"
        systemctl --user status $SERVICE_NAME
        ;;
    logs)
        echo "Datatracker service logs:"
        journalctl --user -u $SERVICE_NAME -f
        ;;
    enable)
        echo "Enabling datatracker service to start on login..."
        reload_daemon_if_needed
        systemctl --user enable $SERVICE_NAME
        ;;
    disable)
        echo "Disabling datatracker service..."
        systemctl --user disable $SERVICE_NAME
        ;;
    reload)
        echo "Reloading systemd user daemon..."
        systemctl --user daemon-reload
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|enable|disable|reload}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the service"
        echo "  stop    - Stop the service"
        echo "  restart - Restart the service"
        echo "  status  - Show service status"
        echo "  logs    - Show service logs (follow)"
        echo "  enable  - Enable service to start on login"
        echo "  disable - Disable service"
        echo "  reload  - Reload systemd daemon configuration"
        exit 1
        ;;
esac