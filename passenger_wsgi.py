import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Set environment variable for cPanel
os.environ['CPANEL'] = '1'

# Import the Flask app
from app import app

# For cPanel deployment
application = app

if __name__ == '__main__':
    application.run() 