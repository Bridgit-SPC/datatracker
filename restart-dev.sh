#!/bin/bash
# Quick script to restart dev service

systemctl --user restart datatracker-dev.service
sleep 3
systemctl --user status datatracker-dev.service --no-pager | head -10

echo ""
echo "Service restarted. Check https://dev.rfc.themetalayer.org"
