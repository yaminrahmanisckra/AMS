#!/bin/bash
# Check routes.py file on server for indentation issues

cd /home/gronthon/kulawams.xyz/blueprints/routine_management

echo "=== Checking routes.py file ==="
echo ""

# Check for tabs (should be 0)
echo "1. Checking for tabs..."
TAB_COUNT=$(sed -n '193,195p' routes.py | grep -c $'\t' || echo "0")
echo "Tabs found: $TAB_COUNT"
echo ""

# Show exact characters
echo "2. Exact content (cat -A shows all characters):"
sed -n '192,196p' routes.py | cat -A
echo ""

# Check indentation
echo "3. Indentation check:"
sed -n '193,194p' routes.py | while IFS= read -r line; do
    LEADING=$(echo "$line" | sed 's/[^ ].*//')
    SPACE_COUNT=$(echo "$LEADING" | wc -c)
    echo "Line: ${line:0:50}"
    echo "  Leading spaces: $((SPACE_COUNT - 1))"
done
echo ""

# Try Python compile
echo "4. Python syntax check:"
python -m py_compile routes.py 2>&1 || echo "Syntax error found!"
echo ""

# Check file encoding
echo "5. File encoding:"
file routes.py
echo ""

echo "=== Done ==="
