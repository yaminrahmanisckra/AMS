#!/usr/bin/env python3
"""
Script to create the batch_custom_event table in the database
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from extensions import db

def create_batch_custom_event_table():
    """Create the batch_custom_event table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Import the model to register it with SQLAlchemy
            from blueprints.academic_calendar.models import BatchCustomEvent
            
            # Create all tables (this will create batch_custom_event if it doesn't exist)
            db.create_all()
            
            print("✓ Successfully created/verified 'batch_custom_event' table")
            print("✓ Table is ready for use")
            
        except Exception as e:
            print(f"✗ Error creating table: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    create_batch_custom_event_table()
