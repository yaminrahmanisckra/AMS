#!/bin/bash
# Diagnostic script for cPanel application issues after file replacement
# Run this on cPanel server: cd ~/aqpub.com && bash diagnose_cpanel_issue.sh

echo "=========================================="
echo "cPanel Application Diagnostic Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check Error Logs
echo "=== Step 1: Checking Error Logs ==="
echo ""

if [ -f "logs/passenger_startup_errors.log" ]; then
    echo -e "${RED}STARTUP ERRORS FOUND:${NC}"
    tail -50 logs/passenger_startup_errors.log
    echo ""
else
    echo -e "${GREEN}✓ No passenger_startup_errors.log found (may be normal if no errors)${NC}"
    echo ""
fi

if [ -f "logs/app_errors.log" ]; then
    echo -e "${YELLOW}Recent Application Errors:${NC}"
    tail -20 logs/app_errors.log | grep -i error | tail -5
    echo ""
else
    echo -e "${YELLOW}⚠ logs/app_errors.log not found${NC}"
    echo ""
fi

# Step 2: Verify Critical Files
echo "=== Step 2: Verifying Critical Files ==="
echo ""

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1 exists"
        if [ -r "$1" ]; then
            echo -e "  ${GREEN}  Readable${NC}"
        else
            echo -e "  ${RED}  NOT READABLE${NC}"
        fi
    else
        echo -e "${RED}✗${NC} $1 MISSING"
    fi
}

check_file "app.py"
check_file "passenger_wsgi.py"
check_file "requirements.txt"
check_file "extensions.py"
check_file ".env"

echo ""

# Check .env content (without showing sensitive data)
if [ -f ".env" ]; then
    echo "Checking .env file content..."
    if grep -q "DATABASE_URL" .env; then
        echo -e "${GREEN}✓${NC} DATABASE_URL found in .env"
    else
        echo -e "${RED}✗${NC} DATABASE_URL NOT found in .env"
    fi
    
    if grep -q "SECRET_KEY" .env; then
        echo -e "${GREEN}✓${NC} SECRET_KEY found in .env"
    else
        echo -e "${RED}✗${NC} SECRET_KEY NOT found in .env"
    fi
    echo ""
fi

# Step 3: Check File Permissions
echo "=== Step 3: Checking File Permissions ==="
echo ""

check_perm() {
    file="$1"
    expected="$2"
    if [ -e "$file" ]; then
        actual=$(stat -c "%a" "$file" 2>/dev/null || stat -f "%OLp" "$file" 2>/dev/null)
        if [ "$actual" = "$expected" ] || [ "$actual" = "0$expected" ]; then
            echo -e "${GREEN}✓${NC} $file: $actual (expected: $expected)"
        else
            echo -e "${YELLOW}⚠${NC} $file: $actual (expected: $expected)"
        fi
    fi
}

check_perm "app.py" "644"
check_perm "passenger_wsgi.py" "644"
check_perm ".env" "644"
check_perm "requirements.txt" "644"

if [ -d "blueprints" ]; then
    perm=$(stat -c "%a" blueprints 2>/dev/null || stat -f "%OLp" blueprints 2>/dev/null)
    if [ "$perm" = "755" ] || [ "$perm" = "0755" ]; then
        echo -e "${GREEN}✓${NC} blueprints/: $perm"
    else
        echo -e "${YELLOW}⚠${NC} blueprints/: $perm (expected: 755)"
    fi
fi

echo ""

# Step 4: Test Application Import
echo "=== Step 4: Testing Application Import ==="
echo ""

# Find Python version in virtualenv
VENV_PYTHON=""
if [ -d ~/virtualenv/aqpub.com ]; then
    for version in 3.12 3.11 3.10 3.9 3.8; do
        if [ -f ~/virtualenv/aqpub.com/$version/bin/python3 ]; then
            VENV_PYTHON=~/virtualenv/aqpub.com/$version/bin/python3
            echo "Found Python: $VENV_PYTHON"
            break
        fi
    done
fi

if [ -z "$VENV_PYTHON" ]; then
    echo -e "${YELLOW}⚠ Virtual environment Python not found, using system Python${NC}"
    VENV_PYTHON=python3
fi

echo "Testing application import..."
$VENV_PYTHON -c "from app import create_app; app = create_app(); print('SUCCESS: Application imported')" 2>&1
IMPORT_RESULT=$?

if [ $IMPORT_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓ Application import successful${NC}"
else
    echo -e "${RED}✗ Application import FAILED${NC}"
fi
echo ""

# Step 5: Verify Dependencies
echo "=== Step 5: Verifying Dependencies ==="
echo ""

if [ -n "$VENV_PYTHON" ] && [ "$VENV_PYTHON" != "python3" ]; then
    echo "Checking installed packages..."
    $VENV_PYTHON -m pip list 2>/dev/null | grep -E "(flask|weasyprint|pandas|reportlab)" || echo "Could not check packages"
    echo ""
fi

# Summary
echo "=========================================="
echo "Diagnostic Summary"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Review error logs above"
echo "2. Fix any missing files or permissions"
echo "3. Restart application: touch passenger_wsgi.py"
echo "4. Check application status in cPanel"
echo ""

