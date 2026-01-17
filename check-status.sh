#!/bin/bash
# Check deployment status and write results to file

OUTPUT="/tmp/deployment-status.txt"
echo "=== DEPLOYMENT STATUS $(date) ===" > $OUTPUT

echo "1. Checking dev service..." >> $OUTPUT
systemctl --user is-active datatracker-dev.service >> $OUTPUT 2>&1
systemctl --user status datatracker-dev.service --no-pager | head -5 >> $OUTPUT 2>&1

echo -e "\n2. Testing localhost..." >> $OUTPUT
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8001/ >> $OUTPUT 2>&1

echo -e "\n3. Testing dev subdomain..." >> $OUTPUT
curl -s -o /dev/null -w "HTTP %{http_code}\n" https://dev.rfc.themetalayer.org/ >> $OUTPUT 2>&1

echo -e "\n4. Checking for new text (localhost)..." >> $OUTPUT
TEXT_LOCAL=$(curl -s http://localhost:8001/ 2>&1 | grep -o "Welcome to the Meta-Layer Governance Hub" | head -1)
echo "Found: '$TEXT_LOCAL'" >> $OUTPUT

echo -e "\n5. Checking for new text (dev subdomain)..." >> $OUTPUT
TEXT_DEV=$(curl -s https://dev.rfc.themetalayer.org/ 2>&1 | grep -o "Welcome to the Meta-Layer Governance Hub" | head -1)
echo "Found: '$TEXT_DEV'" >> $OUTPUT

echo -e "\n6. Nginx config..." >> $OUTPUT
cat /etc/nginx/sites-enabled/dev.rfc.themetalayer.org | grep -E "server_name|proxy_pass|listen" | head -10 >> $OUTPUT 2>&1

echo -e "\n=== CHECK RESULTS ===" >> $OUTPUT
if [ "$TEXT_DEV" == "Welcome to the Meta-Layer Governance Hub" ]; then
    echo "SUCCESS: New text found on dev subdomain!" >> $OUTPUT
elif [ "$TEXT_LOCAL" == "Welcome to the Meta-Layer Governance Hub" ]; then
    echo "SUCCESS: New text found on localhost (nginx issue)" >> $OUTPUT
else
    echo "FAILED: New text not found anywhere" >> $OUTPUT
fi

echo "=== END $(date) ===" >> $OUTPUT

echo ""
echo "Status check complete. Results saved to: $OUTPUT"
echo "To view results: cat $OUTPUT"
