# MLTF Datatracker Deployment Guide

This guide explains how to manage the production and development environments for the MLTF Datatracker.

## Environments

- **Production**: `rfc.themetalayer.org` (port 8000)
- **Development**: `localhost:8001` (or configure nginx for dev subdomain)

## Quick Start

### Initial Setup

1. **Setup development environment** (first time only):
   ```bash
   cd /home/ubuntu/datatracker
   ./setup-dev.sh
   ```

2. **Deploy to production**:
   ```bash
   ./deploy.sh production
   ```

3. **Deploy to development**:
   ```bash
   ./deploy.sh development
   ```

## Service Management

### Production Service

```bash
# Start/Stop/Restart
systemctl --user start datatracker.service
systemctl --user stop datatracker.service
systemctl --user restart datatracker.service

# Check status
systemctl --user status datatracker.service

# View logs
journalctl --user -u datatracker.service -f
```

### Development Service

```bash
# Start/Stop/Restart
systemctl --user start datatracker-dev.service
systemctl --user stop datatracker-dev.service
systemctl --user restart datatracker-dev.service

# Check status
systemctl --user status datatracker-dev.service

# View logs
journalctl --user -u datatracker-dev.service -f
```

## Database Management

### Database Locations

- **Production**: `/home/ubuntu/datatracker/instance/datatracker.db`
- **Development**: `/home/ubuntu/datatracker/instance_dev/datatracker_dev.db`

### Copy Production to Development

To test with production data:

```bash
./migrate-to-dev.sh
```

This will:
1. Stop the dev service
2. Backup existing dev database
3. Copy production database to dev
4. Restart dev service

## Deployment Workflow

### Zero-Downtime Production Deployment

1. **Test changes in development first**:
   ```bash
   # Make your changes
   ./deploy.sh development
   # Test at http://localhost:8001
   ```

2. **Deploy to production**:
   ```bash
   ./deploy.sh production
   ```

The deployment script:
- Creates a database backup automatically
- Pulls latest code (if using git)
- Updates dependencies
- Initializes database (runs migrations)
- Restarts the service with zero downtime

### Manual Deployment Steps

If you need more control:

```bash
# 1. Backup database
cp instance/datatracker.db backups/datatracker.db.$(date +%Y%m%d_%H%M%S)

# 2. Pull code (if using git)
git pull

# 3. Update dependencies
pip3 install -r requirements.txt

# 4. Restart service
systemctl --user restart datatracker.service
```

## Environment Variables

The application uses these environment variables:

- `FLASK_ENV`: `production` or `development` (default: `production`)
- `FLASK_PORT`: Port number (default: 8000 for prod, 8001 for dev)
- `SECRET_KEY`: Secret key for sessions (change in production!)

## Troubleshooting

### Service won't start

1. Check logs:
   ```bash
   journalctl --user -u datatracker.service -n 50
   ```

2. Test manually:
   ```bash
   cd /home/ubuntu/datatracker
   FLASK_ENV=production python3 ietf_data_viewer_simple.py
   ```

### Database issues

1. Check database file exists:
   ```bash
   ls -lh instance/datatracker.db
   ```

2. Check permissions:
   ```bash
   chmod 644 instance/datatracker.db
   ```

### Port conflicts

If port 8000 or 8001 is already in use:

```bash
# Find what's using the port
sudo lsof -i :8000
sudo lsof -i :8001

# Kill the process or change FLASK_PORT
```

## Backup and Recovery

### Manual Backup

```bash
# Create backup directory
mkdir -p backups/$(date +%Y%m%d)

# Backup database
cp instance/datatracker.db backups/$(date +%Y%m%d)/datatracker.db

# Backup uploads (if any)
cp -r uploads backups/$(date +%Y%m%d)/uploads
```

### Restore from Backup

```bash
# Stop service
systemctl --user stop datatracker.service

# Restore database
cp backups/YYYYMMDD/datatracker.db instance/datatracker.db

# Restart service
systemctl --user start datatracker.service
```

## Development Workflow

1. **Make changes** to code
2. **Test in development**:
   ```bash
   ./deploy.sh development
   # Test at http://localhost:8001
   ```
3. **If tests pass, deploy to production**:
   ```bash
   ./deploy.sh production
   ```

## Notes

- Production database is automatically backed up before each deployment
- Development environment uses a separate database (won't affect production)
- Both environments can run simultaneously
- Production runs on port 8000 (nginx proxy)
- Development runs on port 8001 (direct access)
