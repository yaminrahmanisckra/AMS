#!/bin/bash
# Network Access Test Script for Academic Management System

echo "=========================================="
echo "Network Access Test Script"
echo "=========================================="
echo ""

# Get local IP
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)

if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi

echo "1. Local IP Address: $LOCAL_IP"
echo ""

# Check if app is running
echo "2. Checking if app is running on port 5001..."
if lsof -i :5001 > /dev/null 2>&1; then
    echo "   ✅ Port 5001 is in use (app is likely running)"
else
    echo "   ❌ Port 5001 is not in use (app is not running)"
    echo "   Start the app with: ALLOW_NETWORK_ACCESS=1 python3 app.py"
fi
echo ""

# Test localhost access
echo "3. Testing localhost access..."
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/ | grep -q "200\|302\|301"; then
    echo "   ✅ Localhost access: http://127.0.0.1:5001 (WORKING)"
else
    echo "   ❌ Localhost access: http://127.0.0.1:5001 (NOT WORKING)"
fi
echo ""

# Test network access
if [ ! -z "$LOCAL_IP" ]; then
    echo "4. Testing network access..."
    if curl -s -o /dev/null -w "%{http_code}" http://$LOCAL_IP:5001/ --max-time 3 | grep -q "200\|302\|301"; then
        echo "   ✅ Network access: http://$LOCAL_IP:5001 (WORKING)"
    else
        echo "   ❌ Network access: http://$LOCAL_IP:5001 (NOT WORKING)"
        echo "   Possible issues:"
        echo "   - Firewall blocking port 5001"
        echo "   - App not running with ALLOW_NETWORK_ACCESS=1"
    fi
    echo ""
fi

# Check firewall status (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "5. Checking macOS Firewall..."
    FIREWALL_STATUS=$(/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null | grep -i "enabled")
    if [ ! -z "$FIREWALL_STATUS" ]; then
        echo "   ⚠️  Firewall is enabled"
        echo "   To allow Python:"
        echo "   System Preferences → Security & Privacy → Firewall → Firewall Options"
        echo "   Add Python to allowed applications"
    else
        echo "   ✅ Firewall is disabled or not configured"
    fi
    echo ""
fi

echo "=========================================="
echo "Access URLs:"
echo "=========================================="
echo "Local:    http://127.0.0.1:5001"
if [ ! -z "$LOCAL_IP" ]; then
    echo "Network:  http://$LOCAL_IP:5001"
fi
echo ""
echo "From other devices on same WiFi:"
if [ ! -z "$LOCAL_IP" ]; then
    echo "  http://$LOCAL_IP:5001"
fi
echo ""
echo "Troubleshooting:"
echo "1. Make sure app is running: ALLOW_NETWORK_ACCESS=1 python3 app.py"
echo "2. Check firewall settings"
echo "3. Verify both devices are on same network"
echo "4. Try accessing from browser: http://$LOCAL_IP:5001"
echo "=========================================="

