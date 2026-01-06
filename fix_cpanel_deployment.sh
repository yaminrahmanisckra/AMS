#!/bin/bash
# Fix script for cPanel deployment issues after file replacement
# Run this on cPanel server: cd ~/aqpub.com && bash fix_cpanel_deployment.sh

echo "=========================================="
echo "cPanel Application Fix Script"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Find Python version
VENV_PYTHON=""
if [ -d ~/virtualenv/aqpub.com ]; then
    for version in 3.12 3.11 3.10 3.9 3.8; do
        if [ -f ~/virtualenv/aqpub.com/$version/bin/python3 ]; then
            VENV_PYTHON=~/virtualenv/aqpub.com/$version/bin/python3
            break
        fi
    done
fi

if [ -z "$VENV_PYTHON" ]; then
    VENV_PYTHON=python3
fi

echo "Using Python: $VENV_PYTHON"
echo ""

# Fix 1: Check and restore .env file
echo "=== Fix 1: Checking .env file ==="
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ .env file is MISSING${NC}"
    echo "Creating .env file template..."
    cat > .env << 'EOF'
# Flask Configuration
SECRET_KEY=your_secret_key_here_CHANGE_THIS
DATABASE_URL=mysql+pymysql://username:password@localhost/database_name
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
CPANEL=1
EOF
    echo -e "${YELLOW}⚠ Created .env template - YOU MUST EDIT IT WITH CORRECT VALUES${NC}"
    echo ""
elif [ ! -s ".env" ]; then
    echo -e "${RED}✗ .env file is EMPTY${NC}"
    echo "Please restore .env file with correct values"
    echo ""
else
    echo -e "${GREEN}✓ .env file exists${NC}"
    if ! grep -q "DATABASE_URL" .env; then
        echo -e "${YELLOW}⚠ DATABASE_URL not found in .env${NC}"
    fi
    if ! grep -q "SECRET_KEY" .env; then
        echo -e "${YELLOW}⚠ SECRET_KEY not found in .env${NC}"
    fi
    echo ""
fi

# Fix 2: Fix file permissions
echo "=== Fix 2: Fixing File Permissions ==="
chmod 644 *.py *.txt .htaccess 2>/dev/null
chmod 644 .env 2>/dev/null
chmod 755 blueprints/ templates/ static/ logs/ instance/ 2>/dev/null
echo -e "${GREEN}✓ File permissions set${NC}"
echo ""

# Fix 3: Verify passenger_wsgi.py
echo "=== Fix 3: Verifying passenger_wsgi.py ==="
if [ -f "passenger_wsgi.py" ]; then
    if grep -q "passenger_startup_errors.log" passenger_wsgi.py; then
        echo -e "${GREEN}✓ passenger_wsgi.py has error handling${NC}"
    else
        echo -e "${YELLOW}⚠ passenger_wsgi.py may need update${NC}"
        echo "Consider pulling latest version from git"
    fi
else
    echo -e "${RED}✗ passenger_wsgi.py MISSING${NC}"
fi
echo ""

# Fix 4: Check dependencies
echo "=== Fix 4: Checking Dependencies ==="
if [ "$VENV_PYTHON" != "python3" ]; then
    echo "Checking critical packages..."
    MISSING_PACKAGES=()
    
    $VENV_PYTHON -c "import flask" 2>/dev/null || MISSING_PACKAGES+=("flask")
    $VENV_PYTHON -c "import flask_sqlalchemy" 2>/dev/null || MISSING_PACKAGES+=("flask-sqlalchemy")
    $VENV_PYTHON -c "import flask_login" 2>/dev/null || MISSING_PACKAGES+=("flask-login")
    
    if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠ Missing packages: ${MISSING_PACKAGES[*]}${NC}"
        echo "To install: $VENV_PYTHON -m pip install -r requirements.txt"
    else
        echo -e "${GREEN}✓ Critical packages installed${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Could not verify packages (using system Python)${NC}"
fi
echo ""

# Fix 5: Test application
echo "=== Fix 5: Testing Application ==="
echo "Testing import..."
$VENV_PYTHON -c "from app import create_app; app = create_app(); print('SUCCESS')" 2>&1 | head -5
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Application can be imported${NC}"
else
    echo -e "${RED}✗ Application import FAILED - check error logs${NC}"
fi
echo ""

# Summary
echo "=========================================="
echo "Fix Summary"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. If .env was created, edit it with correct values"
echo "2. If packages are missing, run: $VENV_PYTHON -m pip install -r requirements.txt"
echo "3. Restart application: touch passenger_wsgi.py"
echo "4. Check cPanel → Software → Setup Python App → Restart"
echo ""




