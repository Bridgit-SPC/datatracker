# Agent Deployment Workflow

## Overview
The deployment system has been refactored for AI agents to reliably deploy code changes without requiring user intervention.

## Agent Deployment Command

**For Development:**
```bash
cd /home/ubuntu/datatracker
./agent-deploy.sh development
```

**For Production:**
```bash
./agent-deploy.sh production
```

## What the Agent Script Does

1. **Stops the service** - Clean shutdown
2. **Clears Python cache** - Removes old bytecode files
3. **Verifies code** - Checks expected changes are present
4. **Starts service** - Restarts with new code
5. **Tests HTTP** - Verifies service is responding
6. **Checks content** - Verifies expected changes are live
7. **Returns status** - Clear success/failure indication

## Output Format

The script uses agent-readable markers:
- `AGENT_DEPLOY_START|ENV=development` - Deployment started
- `AGENT_STATUS|message` - Progress update
- `AGENT_RESULT|SUCCESS|message` - Success with details
- `AGENT_RESULT|ERROR|message` - Failure with details
- `AGENT_DEPLOY_END` - Process complete

## Agent Workflow Example

```python
# Agent makes code change
# Then runs:
result = subprocess.run(['./agent-deploy.sh', 'development'], 
                       capture_output=True, text=True)

if "AGENT_RESULT|SUCCESS" in result.stdout:
    # Deployment successful
    # Can proceed to production if needed
    subprocess.run(['./agent-deploy.sh', 'production'])
else:
    # Deployment failed - check output
    print(result.stdout)
```

## Deployment API Endpoints

The application now includes deployment status endpoints:

### Check Status
```bash
curl http://localhost:8001/_deploy/status
```

Returns JSON:
```json
{
  "environment": "development",
  "port": 8001,
  "database": "/path/to/db",
  "code_version": "2026-01-17",
  "has_new_text": true,
  "service_active": true
}
```

### Reload (Dev Only)
```bash
curl -X POST http://localhost:8001/_deploy/reload
```

Clears cache and returns restart instructions.

## Integration with deploy.sh

The main `deploy.sh` script now automatically uses `agent-deploy.sh` for reliable deployment. Agents can use either:

- `./deploy.sh development` - Full deployment with backups
- `./agent-deploy.sh development` - Direct agent deployment

## Verification After Deployment

Agents can verify deployment:

```python
import urllib.request
import json

# Check status
response = urllib.request.urlopen('http://localhost:8001/_deploy/status')
status = json.loads(response.read())
print(f"Service active: {status['service_active']}")
print(f"Has new text: {status['has_new_text']}")

# Check content
response = urllib.request.urlopen('http://localhost:8001/')
content = response.read().decode('utf-8')
if 'Welcome to the Meta-Layer Governance Hub' in content:
    print("✓ Deployment verified")
```

## Key Features

1. **Agent-readable output** - Clear status markers
2. **Automatic verification** - Tests HTTP and content
3. **Error handling** - Clear error messages
4. **No user intervention** - Fully automated
5. **Status API** - Programmatic status checking

## Next Steps for Agents

1. Make code changes
2. Run: `./agent-deploy.sh development`
3. Check output for `AGENT_RESULT|SUCCESS`
4. Verify: `curl http://localhost:8001/_deploy/status`
5. If good: `./agent-deploy.sh production`
