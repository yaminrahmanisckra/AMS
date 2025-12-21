#!/bin/bash
# Restart script for Academic Management System with WeasyPrint support

echo "=========================================="
echo "Restarting Academic Management System"
echo "=========================================="
echo ""

# Kill any existing app processes
echo "Stopping existing processes..."
pkill -f "python.*app.py" || true
pkill -f "python3.*app.py" || true
sleep 2

# Check if port is still in use
if lsof -i :5001 > /dev/null 2>&1; then
    echo "⚠️  Port 5001 is still in use. Force killing..."
    lsof -ti :5001 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

# Set library paths for WeasyPrint on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
    export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH
    echo "✓ Set WeasyPrint library paths for macOS"
fi

# Verify WeasyPrint can be imported
echo ""
echo "Verifying WeasyPrint installation..."
if [ -f ".venv/bin/python" ]; then
    export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
    export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH
    .venv/bin/python -c "from weasyprint import HTML; print('✓ WeasyPrint is ready')" 2>/dev/null && echo "✓ WeasyPrint verification successful" || echo "⚠️  WeasyPrint import failed in .venv"
elif [ -f "venv/bin/python" ]; then
    export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
    export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH
    venv/bin/python -c "from weasyprint import HTML; print('✓ WeasyPrint is ready')" 2>/dev/null && echo "✓ WeasyPrint verification successful" || echo "⚠️  WeasyPrint import failed in venv"
else
    python3 -c "from weasyprint import HTML; print('✓ WeasyPrint is ready')" 2>/dev/null && echo "✓ WeasyPrint verification successful" || echo "⚠️  WeasyPrint import failed - check installation"
fi

echo ""
echo "Starting server..."
echo ""

# Check if .venv exists and use it, otherwise use system Python
if [ -f ".venv/bin/python" ]; then
    echo "✓ Using .venv (Python 3.11)"
    ALLOW_NETWORK_ACCESS=1 .venv/bin/python app.py
elif [ -f "venv/bin/python" ]; then
    echo "✓ Using venv"
    ALLOW_NETWORK_ACCESS=1 venv/bin/python app.py
else
    echo "⚠️  No virtual environment found, using system Python"
    ALLOW_NETWORK_ACCESS=1 python3 app.py
fi
