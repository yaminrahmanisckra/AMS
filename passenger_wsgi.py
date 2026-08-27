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
activate_this = os.environ.get(
    'VIRTUALENV_ACTIVATE',
    '/home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate_this.py',
)
if os.path.exists(activate_this):
    with open(activate_this) as file_:
        exec(file_.read(), dict(__file__=activate_this))

# Set environment variables for cPanel
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('CPANEL', '1')
os.environ.setdefault('MYSQL', '1')

# Prefer private log dir outside document root (create on host: /home/<user>/ams_logs)
_home = os.path.expanduser('~')
_default_log_dir = os.path.join(_home, 'ams_logs')
LOG_DIR = os.environ.get('AMS_LOG_DIR', _default_log_dir)
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except OSError:
    LOG_DIR = os.path.join(BASE_DIR, 'logs')
    os.makedirs(LOG_DIR, exist_ok=True)
# Ensure app error_handler uses the same directory
os.environ.setdefault('AMS_LOG_DIR', LOG_DIR)

LOG_PATH = os.path.join(LOG_DIR, 'passenger_wsgi.log')
ERROR_PATH = os.path.join(LOG_DIR, 'startup_error.log')

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

try:
    from app import create_app
    application = create_app()
    logging.info('Application created successfully')
    try:
        from blueprints.admission_exam.routes import ADMIT_PDF_ENGINE
        logging.info('Admit PDF engine loaded: %s', ADMIT_PDF_ENGINE)
    except Exception as eng_err:
        logging.warning('Admit PDF engine import failed: %s', eng_err)
except Exception as e:
    error_msg = traceback.format_exc()
    logging.error('Failed to create application: %s', error_msg)
    try:
        with open(ERROR_PATH, 'w') as f:
            f.write(error_msg)
    except OSError:
        pass
    # Do not write startup_error.log into the document root
    raise

handler = logging.FileHandler(LOG_PATH)
handler.setLevel(logging.ERROR)
application.logger.addHandler(handler)

if __name__ == '__main__':
    application.run(debug=False, host='0.0.0.0', port=5000)
