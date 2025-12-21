#!/bin/bash
# Simple launcher that sets up environment for WeasyPrint

# Set library paths for WeasyPrint on macOS BEFORE starting Python
if [[ "$OSTYPE" == "darwin"* ]]; then
    export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
    export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH
    export PKG_CONFIG_PATH=/opt/homebrew/lib/pkgconfig:$PKG_CONFIG_PATH
    echo "✓ Set WeasyPrint library paths for macOS"
fi

# Use .venv if available, otherwise system Python
if [ -f ".venv/bin/python" ]; then
    echo "✓ Using .venv (Python 3.11)"
    ALLOW_NETWORK_ACCESS=1 .venv/bin/python app.py "$@"
elif [ -f "venv/bin/python" ]; then
    echo "✓ Using venv"
    ALLOW_NETWORK_ACCESS=1 venv/bin/python app.py "$@"
else
    echo "⚠️  Using system Python (no virtual environment)"
    ALLOW_NETWORK_ACCESS=1 python3 app.py "$@"
fi
