#!/bin/bash
# Script to check Passenger and application status for kulawams.xyz

cd /home/gronthon/kulawams.xyz

echo "=== 1. PHP Error Log (Recent Errors) ==="
tail -30 ~/logs/.php.error.log 2>/dev/null | grep -i "kulawams\|passenger\|error" | tail -20

echo -e "\n=== 2. Passenger Process Check ==="
ps aux | grep -i passenger | grep -v grep

echo -e "\n=== 3. Check .htaccess Syntax ==="
grep -i passenger .htaccess | head -7

echo -e "\n=== 4. Check passenger_wsgi.py ==="
ls -la passenger_wsgi.py
head -5 passenger_wsgi.py

echo -e "\n=== 5. Test Python App Directly ==="
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
python -c "from app import create_app; app = create_app(); print('✅ App loads OK')" 2>&1

echo -e "\n=== 6. Check Addon Domain Document Root ==="
# Check if symlink or directory exists
ls -ld /home/gronthon/kulawams.xyz 2>/dev/null

echo -e "\n=== 7. Check tmp/restart.txt ==="
ls -la tmp/restart.txt 2>/dev/null || echo "tmp/restart.txt not found (create it: touch tmp/restart.txt)"

echo -e "\n=== Done ==="
