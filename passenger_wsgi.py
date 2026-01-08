#!/usr/bin/env python3
"""
Passenger WSGI file for cPanel Python application deployment
This file is required for cPanel to run Python applications
"""

import os
import sys

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Set environment variables for cPanel
os.environ['CPANEL'] = '1'
os.environ['FLASK_ENV'] = 'production'

# Import the Flask application
from app import create_app

# Create the application instance
application = create_app()

# For debugging purposes
if __name__ == '__main__':
    application.run(debug=False, host='0.0.0.0', port=5000) 