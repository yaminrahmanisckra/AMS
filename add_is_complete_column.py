#!/usr/bin/env python3
"""
Add is_complete column to exam_scrutinizer_invite table
Works with both SQLite and MySQL databases
"""

from app import create_app
from extensions import db
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    try:
        # Get database dialect
        dialect = db.engine.dialect.name
        print(f"Database dialect: {dialect}")
        
        # Check which columns exist
        inspector = inspect(db.engine)
        table_name = 'exam_scrutinizer_invite'
        
        try:
            existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
            print(f"Existing columns in {table_name}: {existing_columns}")
        except Exception as e:
            print(f"Error checking table: {e}")
            print("Table might not exist yet. This is okay if you're setting up a new database.")
            exit(0)
        
        column_name = 'is_complete'
        
        if column_name not in existing_columns:
            try:
                if dialect == 'sqlite':
                    # SQLite doesn't support BOOLEAN, use INTEGER with 0/1
                    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} INTEGER NOT NULL DEFAULT 0"))
                    print(f"✓ Added column: {column_name} (as INTEGER for SQLite)")
                else:  # MySQL, PostgreSQL, etc.
                    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} BOOLEAN NOT NULL DEFAULT FALSE"))
                    print(f"✓ Added column: {column_name} (as BOOLEAN)")
                
                db.session.commit()
                print(f"\n✓ Successfully added {column_name} column to {table_name} table!")
            except Exception as e:
                db.session.rollback()
                print(f"✗ Error adding {column_name}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"- Column {column_name} already exists in {table_name}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
