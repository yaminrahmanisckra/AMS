#!/bin/bash
# Check for .htaccess conflict between main folder and addon domain

echo "=== Checking .htaccess Files ==="
echo ""

# Main folder
echo "1. Main folder /home/gronthon/.htaccess:"
if [ -f /home/gronthon/.htaccess ]; then
    echo "   ✅ EXISTS"
    echo "   Size: $(wc -l < /home/gronthon/.htaccess) lines"
    echo "   First 15 lines:"
    head -15 /home/gronthon/.htaccess | sed 's/^/   /'
    echo ""
    echo "   Contains Passenger config:"
    grep -i passenger /home/gronthon/.htaccess | head -3 | sed 's/^/   /' || echo "   ❌ No Passenger config"
else
    echo "   ❌ NOT FOUND"
fi
echo ""

# Addon domain
echo "2. Addon domain /home/gronthon/kulawams.xyz/.htaccess:"
if [ -f /home/gronthon/kulawams.xyz/.htaccess ]; then
    echo "   ✅ EXISTS"
    echo "   Size: $(wc -l < /home/gronthon/kulawams.xyz/.htaccess) lines"
    echo "   Passenger config:"
    grep -i passenger /home/gronthon/kulawams.xyz/.htaccess | head -7 | sed 's/^/   /'
else
    echo "   ❌ NOT FOUND - THIS IS THE PROBLEM!"
fi
echo ""

# Check for conflicts
echo "3. Potential Conflicts:"
if [ -f /home/gronthon/.htaccess ] && [ -f /home/gronthon/kulawams.xyz/.htaccess ]; then
    echo "   ⚠️  Both .htaccess files exist"
    echo "   Main folder .htaccess might be overriding addon domain .htaccess"
    echo "   Solution: Make main .htaccess domain-specific or exclude addon domains"
fi
echo ""

echo "=== Done ==="
