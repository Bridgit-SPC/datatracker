# MLTF Datatracker Service Management

The Flask application is now managed by a systemd user service for reliable operation.

## Service Status
- **Location**: `~/.config/systemd/user/datatracker.service`
- **Port**: 8000 (proxied by Nginx on port 443)
- **Auto-restart**: Enabled (restarts after 5 seconds if crashed)

## Quick Commands

### Using the Management Script (Recommended)
```bash
cd /home/ubuntu/datatracker

# Start service (auto-reloads daemon if needed)
./manage-service.sh start

# Stop service
./manage-service.sh stop

# Restart service (auto-reloads daemon if needed)
./manage-service.sh restart

# Check status
./manage-service.sh status

# View logs (follow mode)
./manage-service.sh logs

# Manual daemon reload (if needed)
./manage-service.sh reload
```

### Using systemd Directly
```bash
# Start service
systemctl --user start datatracker.service

# Stop service
systemctl --user stop datatracker.service

# Restart service
systemctl --user restart datatracker.service

# Check status
systemctl --user status datatracker.service

# View logs
journalctl --user -u datatracker.service -f

# Enable on login
systemctl --user enable datatracker.service

# Disable on login
systemctl --user disable datatracker.service
```

## Monitoring

The service will:
- ✅ Auto-start when you log in (if enabled)
- ✅ Auto-restart if the Flask app crashes
- ✅ Log all output to systemd journal
- ✅ Run in the background independently of terminal sessions

## Troubleshooting

If the website shows 502 errors:
1. Check service status: `./manage-service.sh status`
2. View recent logs: `./manage-service.sh logs`
3. Restart if needed: `./manage-service.sh restart`

## Production Notes

For production deployment, consider:
- Using Gunicorn instead of Flask dev server
- Setting up proper logging
- Adding health checks
- Using environment-specific configurations