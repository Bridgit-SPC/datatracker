# Firewall Setup for Development Server

## Issue
The development server is running on port 8001 but may be blocked by cloud provider firewall.

## Solution Options

### Option 1: Use SSH Tunnel (Recommended for Security)
Access the dev server through an SSH tunnel from your local machine:

```bash
# On your local machine:
ssh -L 8001:localhost:8001 ubuntu@216.238.91.120

# Then access: http://localhost:8001
```

### Option 2: Open Port 8001 in Cloud Provider Firewall
If using Vultr, DigitalOcean, AWS, etc., you need to open port 8001 in their firewall/security group:

**Vultr:**
1. Go to Vultr dashboard
2. Select your server
3. Go to "Firewall" or "Settings" → "Firewall"
4. Add rule: TCP port 8001, allow from your IP or 0.0.0.0/0

**DigitalOcean:**
1. Go to Networking → Firewalls
2. Add inbound rule: TCP 8001

**AWS:**
1. Go to EC2 → Security Groups
2. Add inbound rule: TCP 8001

### Option 3: Use Nginx Reverse Proxy (Most Secure)
Set up nginx to proxy dev server (similar to production):

```nginx
# /etc/nginx/sites-available/dev.rfc.themetalayer.org
server {
    listen 80;
    server_name dev.rfc.themetalayer.org;
    
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Then only port 80/443 needs to be open (already open for production).

### Option 4: Use Production Port with Different Subdomain
Run dev on port 8000 with a different subdomain, or use a query parameter to switch.

## Quick Test
Test if port is accessible from outside:
```bash
# From your local machine:
curl http://216.238.91.120:8001
```

If it hangs or times out, the firewall is blocking it.
