#!/usr/bin/env python3
"""
Script to create the remuneration_form table in the database.
Run this script once to create the table.
"""

from app import create_app
from extensions import db
from blueprints.remuneration_management.models import RemunerationForm

app = create_app()

with app.app_context():
    try:
        # Create the table
        db.create_all()
        print("✅ RemunerationForm table created successfully!")
        print(f"   Table name: {RemunerationForm.__tablename__}")
        
        # Verify table exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if RemunerationForm.__tablename__ in tables:
            print(f"✅ Verified: Table '{RemunerationForm.__tablename__}' exists in database")
            columns = inspector.get_columns(RemunerationForm.__tablename__)
            print(f"   Columns: {len(columns)}")
        else:
            print(f"⚠️  Warning: Table '{RemunerationForm.__tablename__}' not found")
            
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        import traceback
        traceback.print_exc()















