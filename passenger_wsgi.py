#!/usr/bin/env python3
"""
Passenger WSGI file for cPanel Python application deployment
This file is required for cPanel to run Python applications
"""

import sys
import os
import logging
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Activate virtual environment
activate_this = '/home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate_this.py'
if os.path.exists(activate_this):
    with open(activate_this) as file_:
        exec(file_.read(), dict(__file__=activate_this))

# Set environment variables for cPanel
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('CPANEL', '1')
os.environ.setdefault('MYSQL', '1')

# Setup logging
LOG_PATH = os.path.join(BASE_DIR, 'passenger_wsgi.log')
ERROR_PATH = os.path.join(BASE_DIR, 'startup_error.log')

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

try:
    from app import create_app
    application = create_app()
    logging.info('Application created successfully')
except Exception as e:
    error_msg = traceback.format_exc()
    logging.error(f'Failed to create application: {error_msg}')
    with open(ERROR_PATH, 'w') as f:
        f.write(error_msg)
    raise

# Add error handler to application logger
handler = logging.FileHandler(LOG_PATH)
handler.setLevel(logging.ERROR)
application.logger.addHandler(handler)

# For debugging purposes
if __name__ == '__main__':
    application.run(debug=False, host='0.0.0.0', port=5000) 