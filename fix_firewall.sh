#!/bin/bash
# macOS Firewall Fix Script for Network Access

echo "=========================================="
echo "macOS Firewall Configuration"
echo "=========================================="
echo ""

# Check firewall status
FIREWALL_STATE=$(/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null)
echo "Current Firewall Status: $FIREWALL_STATE"
echo ""

# Find Python executable
PYTHON_PATH=$(which python3)
echo "Python Path: $PYTHON_PATH"
echo ""

echo "To allow Python through firewall:"
echo ""
echo "Method 1: System Preferences (Recommended)"
echo "1. Open: System Preferences → Security & Privacy → Firewall"
echo "2. Click 'Firewall Options' (unlock if needed)"
echo "3. Click '+' button"
echo "4. Navigate to: $PYTHON_PATH"
echo "5. Select Python and click 'Add'"
echo "6. Set to 'Allow incoming connections'"
echo "7. Click 'OK'"
echo ""

echo "Method 2: Command Line (Requires Admin)"
read -p "Do you want to allow Python via command line? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Adding Python to firewall exceptions..."
    sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add "$PYTHON_PATH"
    sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp "$PYTHON_PATH"
    echo "✅ Python has been added to firewall exceptions"
    echo ""
    echo "Verifying..."
    /usr/libexec/ApplicationFirewall/socketfilterfw --listapps | grep -i python || echo "Python not found in list (may need manual setup)"
else
    echo "Skipping command line setup. Please use Method 1 (System Preferences)."
fi

echo ""
echo "=========================================="
echo "After allowing Python, restart the app:"
echo "./start_network.sh"
echo "=========================================="

