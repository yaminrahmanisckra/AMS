#!/bin/bash
# Easy Network Access Startup Script

echo "=========================================="
echo "Starting Academic Management System"
echo "with Network Access Enabled"
echo "=========================================="
echo ""

# Check if port is already in use
if lsof -i :5001 > /dev/null 2>&1; then
    echo "⚠️  Port 5001 is already in use!"
    echo "   Stopping existing process..."
    pkill -f "python3 app.py" || true
    sleep 2
fi

# Get local IP
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)

if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi

echo "📍 Your Local IP: $LOCAL_IP"
echo ""
echo "Starting server..."
echo ""

# Start the app with network access
ALLOW_NETWORK_ACCESS=1 python3 app.py

