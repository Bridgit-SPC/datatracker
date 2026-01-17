# MLTF Datatracker - Quick Reference

## Common Commands

### Deploy
```bash
./deploy.sh production      # Deploy to production (rfc.themetalayer.org)
./deploy.sh development     # Deploy to development (localhost:8001)
```

### Services
```bash
# Production
systemctl --user restart datatracker.service
systemctl --user status datatracker.service
journalctl --user -u datatracker.service -f

# Development
systemctl --user restart datatracker-dev.service
systemctl --user status datatracker-dev.service
journalctl --user -u datatracker-dev.service -f
```

### Database
```bash
# Copy prod to dev for testing
./migrate-to-dev.sh

# Manual backup
cp instance/datatracker.db backups/datatracker.db.$(date +%Y%m%d_%H%M%S)
```

## Environment Details

| Environment | Port | Database | URL |
|------------|------|----------|-----|
| Production | 8000 | `instance/datatracker.db` | https://rfc.themetalayer.org |
| Development | 8001 | `instance_dev/datatracker_dev.db` | http://localhost:8001 |

## Workflow

1. **Develop** → Make changes
2. **Test** → `./deploy.sh development` → Test at localhost:8001
3. **Deploy** → `./deploy.sh production` → Live at rfc.themetalayer.org
