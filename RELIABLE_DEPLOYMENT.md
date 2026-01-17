# Reliable Deployment Guide

## The Problem
Flask services don't automatically reload code changes when the reloader is disabled (which we do for systemd). You need to properly restart services.

## Solution: Use These Scripts

### Quick Restart (Development)
```bash
cd /home/ubuntu/datatracker
./fix-dev.sh
```

This script:
1. Stops the service
2. Clears Python cache
3. Verifies code changes
4. Starts the service
5. Verifies it's working

### Deploy to Development
```bash
./deploy.sh development
```

### Deploy to Production
```bash
./deploy.sh production
```

### Restart Both Services
```bash
./restart-services.sh both
```

## Manual Steps (If Scripts Don't Work)

### For Development:
```bash
# 1. Stop service
systemctl --user stop datatracker-dev.service

# 2. Clear cache
cd /home/ubuntu/datatracker
find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null
find . -name "*.pyc" -delete

# 3. Verify code change
grep "Welcome to the Meta-Layer Governance Hub" ietf_data_viewer_simple.py

# 4. Start service
systemctl --user start datatracker-dev.service

# 5. Wait and check
sleep 5
systemctl --user status datatracker-dev.service

# 6. Test
curl http://localhost:8001/ | grep "Welcome"
```

### For Production:
```bash
systemctl --user stop datatracker.service
sleep 2
systemctl --user start datatracker.service
sleep 3
systemctl --user status datatracker.service
```

## Verification

After restarting, verify it's working:

```bash
# Check service status
systemctl --user status datatracker-dev.service

# Check if port is listening
netstat -tlnp | grep 8001
# or
ss -tlnp | grep 8001

# Test HTTP response
curl http://localhost:8001/

# Check for your change
curl http://localhost:8001/ | grep "Welcome to the Meta-Layer Governance Hub"
```

## Common Issues

### Service won't start
```bash
# Check logs
journalctl --user -u datatracker-dev.service -n 50

# Check for errors
journalctl --user -u datatracker-dev.service | grep -i error
```

### Code change not showing
1. Clear browser cache (Ctrl+Shift+R)
2. Verify code is in file: `grep "your text" ietf_data_viewer_simple.py`
3. Clear Python cache (see manual steps above)
4. Restart service properly (stop, wait, start)

### Port already in use
```bash
# Find what's using the port
sudo lsof -i :8001
# Kill it
kill <PID>
```

## Best Practice Workflow

1. **Make code changes**
2. **Test locally** (if possible)
3. **Deploy to dev**: `./deploy.sh development`
4. **Verify dev**: Visit https://dev.rfc.themetalayer.org
5. **If good, deploy to prod**: `./deploy.sh production`
6. **Verify prod**: Visit https://rfc.themetalayer.org
