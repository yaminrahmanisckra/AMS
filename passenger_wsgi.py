#!/usr/bin/env python3
"""
Passenger WSGI file for cPanel Python application deployment
This file is required for cPanel to run Python applications
"""

import os
import sys

# Get the directory containing this file (application root)
current_dir = os.path.dirname(os.path.abspath(__file__))

# Add the application directory to Python path
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Set environment variables for cPanel
os.environ['CPANEL'] = '1'
os.environ['FLASK_ENV'] = 'production'

# Change to application directory
os.chdir(current_dir)

try:
    # Import the Flask application factory
    from app import create_app
    
    # Create the application instance
    # This is the variable that Passenger/WSGI will use
    application = create_app()
    
except Exception as e:
    # Error handling - log the error
    import traceback
    error_msg = f"Error creating application: {e}\n{traceback.format_exc()}"
    
    # Try to log to a file if possible
    try:
        log_dir = os.path.join(current_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        error_log = os.path.join(log_dir, 'passenger_startup_errors.log')
        with open(error_log, 'a') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Error at: {os.path.basename(__file__)}\n")
            f.write(f"{error_msg}\n")
            f.write(f"{'='*80}\n")
    except:
        pass
    
    # Re-raise the error so Passenger can see it
    raise

# For debugging purposes (only runs if executed directly, not by Passenger)
if __name__ == '__main__':
    application.run(debug=False, host='0.0.0.0', port=5000)
