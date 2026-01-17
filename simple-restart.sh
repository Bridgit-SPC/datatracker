#!/bin/bash
# Simple restart - just restart the service

systemctl --user stop datatracker-dev.service
sleep 3
systemctl --user start datatracker-dev.service
sleep 5
systemctl --user status datatracker-dev.service --no-pager | head -10
