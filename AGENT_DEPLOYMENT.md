# Agent Deployment System

## Overview
This system is designed for AI agents to reliably deploy code changes to development and production environments.

## Agent Deployment Command

```bash
cd /home/ubuntu/datatracker
./agent-deploy.sh development
```

or

```bash
./agent-deploy.sh production
```

## How It Works

1. **Stops the service** - Ensures clean restart
2. **Clears Python cache** - Removes old bytecode
3. **Verifies code** - Checks that expected changes are in file
4. **Starts service** - Restarts with new code
5. **Verifies deployment** - Tests HTTP and checks for expected content
6. **Returns clear status** - Agent-readable output

## Output Format

The script outputs agent-readable status messages:
- `AGENT_DEPLOY_START|ENV=development` - Deployment started
- `AGENT_STATUS|message` - Status update
- `AGENT_RESULT|SUCCESS|message` - Deployment successful
- `AGENT_RESULT|ERROR|message` - Deployment failed
- `AGENT_DEPLOY_END` - Deployment complete

## Deployment API Endpoints

The application also includes API endpoints for deployment status:

### Check Status
```bash
curl http://localhost:8001/_deploy/status
```

Returns JSON with:
- Environment
- Port
- Database path
- Code version
- Whether new text is in code
- Service status

### Reload (Development Only)
```bash
curl -X POST http://localhost:8001/_deploy/reload
```

Clears cache and returns restart command.

## Agent Workflow

1. Make code changes
2. Run: `./agent-deploy.sh development`
3. Check output for `AGENT_RESULT|SUCCESS`
4. If successful, deploy to production: `./agent-deploy.sh production`

## Verification

After deployment, verify:
```bash
curl http://localhost:8001/_deploy/status
curl http://localhost:8001/ | grep "Welcome"
```

## Troubleshooting

If deployment fails:
1. Check service logs: `journalctl --user -u datatracker-dev.service -n 50`
2. Check service status: `systemctl --user status datatracker-dev.service`
3. Check port: `netstat -tlnp | grep 8001`
