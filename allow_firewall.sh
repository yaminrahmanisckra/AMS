#!/bin/bash
# Quick Firewall Allow Script

PYTHON_PATH=$(which python3)
echo "Allowing Python through firewall: $PYTHON_PATH"
echo ""

sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add "$PYTHON_PATH" 2>/dev/null
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp "$PYTHON_PATH" 2>/dev/null

echo "✅ Done! Now restart the app with: ./start_network.sh"

