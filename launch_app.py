#!/usr/bin/env python3
"""
Launcher script for Academic Management System
Sets up WeasyPrint library paths on macOS before importing the app
"""
import os
import sys
import platform

if platform.system() == 'Darwin':  # macOS
    homebrew_lib_path = '/opt/homebrew/lib'
    if os.path.exists(homebrew_lib_path):
        # Set environment variables BEFORE any imports
        os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = f"{homebrew_lib_path}:{os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')}"
        os.environ['DYLD_LIBRARY_PATH'] = f"{homebrew_lib_path}:{os.environ.get('DYLD_LIBRARY_PATH', '')}"
        
        pkg_config_path = '/opt/homebrew/lib/pkgconfig'
        if os.path.exists(pkg_config_path):
            os.environ['PKG_CONFIG_PATH'] = f"{pkg_config_path}:{os.environ.get('PKG_CONFIG_PATH', '')}"

# Set network access flag if not already set
if 'ALLOW_NETWORK_ACCESS' not in os.environ:
    os.environ['ALLOW_NETWORK_ACCESS'] = '1'

# Now import and run the app
if __name__ == '__main__':
    # Import app module
    import app
    
    # Get the Flask app instance
    flask_app = app.create_app()
    
    # Run the app
    flask_app.run(
        host=os.getenv('HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
