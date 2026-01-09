#!/bin/bash
# Final diagnostic to find why site is not loading

cd /home/gronthon/kulawams.xyz

echo "=== 1. Check Current Error Log ==="
cat startup_error.log 2>/dev/null | head -30
echo ""

echo "=== 2. Test App Load Directly ==="
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
python -c "from app import create_app; app = create_app(); print('✅ App OK')" 2>&1
echo ""

echo "=== 3. Check routes.py Syntax ==="
python -m py_compile blueprints/routine_management/routes.py 2>&1
echo ""

echo "=== 4. Check Specific Problem Lines ==="
sed -n '192,196p' blueprints/routine_management/routes.py
echo ""

echo "=== 5. Check File Permissions ==="
ls -la .htaccess passenger_wsgi.py app.py blueprints/routine_management/routes.py | head -5
echo ""

echo "=== 6. Check Passenger Configuration ==="
grep -i passenger .htaccess | head -7
echo ""

echo "=== 7. Check if Passenger Process Running ==="
ps aux | grep -i passenger | grep -v grep || echo "No passenger process found"
echo ""

echo "=== 8. Try to Access Site ==="
curl -I http://kulawams.xyz/ 2>&1 | head -10
echo ""

echo "=== 9. Check cPanel Error Log Location ==="
find ~/logs -name "*error*" -type f 2>/dev/null | head -3
echo ""

echo "=== 10. Check Latest Application Log ==="
tail -20 passenger_wsgi.log 2>/dev/null || echo "No passenger_wsgi.log yet"
echo ""

echo "=== Done ==="
