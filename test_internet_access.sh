#!/bin/bash
# Internet Access Diagnostic Script

echo "=========================================="
echo "Internet Access Diagnostic Tool"
echo "=========================================="
echo ""

# Check if app is running
echo "1. Checking if app is running..."
if lsof -i :5001 > /dev/null 2>&1; then
    echo "   ✅ App is running on port 5001"
    APP_RUNNING=true
else
    echo "   ❌ App is NOT running on port 5001"
    echo "   Start app with: ALLOW_NETWORK_ACCESS=1 python3 app.py"
    APP_RUNNING=false
fi
echo ""

# Get local IP
echo "2. Local IP Address:"
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi
if [ -z "$LOCAL_IP" ]; then
    echo "   ❌ Could not detect local IP"
else
    echo "   ✅ Local IP: $LOCAL_IP"
fi
echo ""

# Get public IP
echo "3. Public IP Address:"
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null)
if [ -z "$PUBLIC_IP" ]; then
    PUBLIC_IP=$(curl -s icanhazip.com 2>/dev/null)
fi
if [ -z "$PUBLIC_IP" ]; then
    echo "   ❌ Could not detect public IP (check internet connection)"
else
    echo "   ✅ Public IP: $PUBLIC_IP"
    echo "   Access URL: http://$PUBLIC_IP:5001"
fi
echo ""

# Check router IP
echo "4. Router/Gateway IP:"
ROUTER_IP=$(netstat -nr | grep default | awk '{print $2}' | head -1)
if [ -z "$ROUTER_IP" ]; then
    ROUTER_IP=$(route -n get default 2>/dev/null | grep gateway | awk '{print $2}')
fi
if [ -z "$ROUTER_IP" ]; then
    echo "   ⚠️  Could not detect router IP"
else
    echo "   ✅ Router IP: $ROUTER_IP"
    echo "   Router Admin: http://$ROUTER_IP"
fi
echo ""

# Test localhost
echo "5. Testing localhost access:"
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001 | grep -q "200\|302\|301"; then
    echo "   ✅ Localhost access working"
else
    echo "   ❌ Localhost access failed"
fi
echo ""

# Test network access
if [ ! -z "$LOCAL_IP" ]; then
    echo "6. Testing network access (local IP):"
    if curl -s -o /dev/null -w "%{http_code}" http://$LOCAL_IP:5001 | grep -q "200\|302\|301"; then
        echo "   ✅ Network access working"
    else
        echo "   ❌ Network access failed"
        echo "   Check firewall settings"
    fi
    echo ""
fi

# Port forwarding check
echo "7. Port Forwarding Status:"
echo "   ⚠️  Manual check required:"
echo "   1. Router admin panel: http://$ROUTER_IP"
echo "   2. Check Port Forwarding section"
echo "   3. Verify rule exists:"
echo "      External Port: 5001"
echo "      Internal IP: $LOCAL_IP"
echo "      Internal Port: 5001"
echo "      Protocol: TCP"
echo ""

# Summary
echo "=========================================="
echo "Summary:"
echo "=========================================="
if [ "$APP_RUNNING" = true ]; then
    echo "✅ App is running"
else
    echo "❌ App is NOT running - Start it first!"
fi

if [ ! -z "$PUBLIC_IP" ]; then
    echo "📍 Public IP: $PUBLIC_IP"
    echo "🌐 Access URL: http://$PUBLIC_IP:5001"
    echo ""
    echo "⚠️  To access from internet:"
    echo "   1. Setup port forwarding in router"
    echo "   2. Use URL: http://$PUBLIC_IP:5001"
    echo "   3. Or use ngrok (easier): ngrok http 5001"
else
    echo "❌ Could not get public IP"
fi

echo ""
echo "📖 For detailed guide, see: INTERNET_ACCESS_GUIDE.md"
echo "=========================================="
