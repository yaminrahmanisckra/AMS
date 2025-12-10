#!/usr/bin/env python3
"""
Script to create the academic_calendar_event table if it doesn't exist.
Run this if migrations are not working.
"""
import os
import sys
from app import create_app, db
from blueprints.academic_calendar.models import AcademicCalendarEvent

def create_table():
    """Create or update the academic_calendar_event table"""
    app = create_app()
    with app.app_context():
        try:
            # Check if table exists
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'academic_calendar_event' in tables:
                print("✓ Table 'academic_calendar_event' already exists.")
                # Check if end_date column exists
                columns = [col['name'] for col in inspector.get_columns('academic_calendar_event')]
                if 'end_date' not in columns:
                    print("⚠ Column 'end_date' missing. Adding column...")
                    try:
                        # For SQLite, we need to recreate the table to add a column
                        from sqlalchemy import text
                        conn = db.engine.connect()
                        # Check if we can alter table (MySQL/PostgreSQL)
                        if db.engine.dialect.name == 'sqlite':
                            # SQLite doesn't support ALTER TABLE ADD COLUMN easily, so recreate
                            print("Recreating table with end_date column...")
                            conn.execute(text("DROP TABLE IF EXISTS academic_calendar_event_backup"))
                            conn.execute(text("""
                                CREATE TABLE academic_calendar_event_backup AS 
                                SELECT id, title, description, event_date, event_type, is_recurring, 
                                       created_by_id, created_at, updated_at 
                                FROM academic_calendar_event
                            """))
                            conn.execute(text("DROP TABLE academic_calendar_event"))
                            db.create_all()
                            conn.execute(text("""
                                INSERT INTO academic_calendar_event 
                                (id, title, description, event_date, event_type, is_recurring, created_by_id, created_at, updated_at)
                                SELECT id, title, description, event_date, event_type, is_recurring, 
                                       created_by_id, created_at, updated_at 
                                FROM academic_calendar_event_backup
                            """))
                            conn.execute(text("DROP TABLE academic_calendar_event_backup"))
                            conn.commit()
                        else:
                            # For other databases, use ALTER TABLE
                            conn.execute(text("ALTER TABLE academic_calendar_event ADD COLUMN end_date DATE"))
                            conn.commit()
                        print("✓ Column 'end_date' added successfully!")
                    except Exception as col_error:
                        print(f"⚠ Could not add end_date column: {col_error}")
                        print("Creating table from scratch...")
                        db.create_all()
                else:
                    print("✓ All columns present.")
                return True
            
            # Create the table
            print("Creating table 'academic_calendar_event'...")
            db.create_all()
            
            # Verify it was created
            tables = db.inspect(db.engine).get_table_names()
            if 'academic_calendar_event' in tables:
                print("✓ Table 'academic_calendar_event' created successfully!")
                return True
            else:
                print("✗ Failed to create table.")
                return False
                
        except Exception as e:
            print(f"✗ Error creating/updating table: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = create_table()
    sys.exit(0 if success else 1)


