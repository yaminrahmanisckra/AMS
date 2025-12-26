"""Script to add new columns to course_outline table for PDF structure"""
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
        if 'course_outline' not in inspector.get_table_names():
            print("Error: course_outline table does not exist!")
            exit(1)
            
        existing_columns = [col['name'] for col in inspector.get_columns('course_outline')]
        print(f"Existing columns: {existing_columns}")
        
        columns_to_add = [
            ('credit_value', 'VARCHAR(20)' if dialect != 'sqlite' else 'TEXT'),
            ('course_type', 'VARCHAR(50)' if dialect != 'sqlite' else 'TEXT'),
            ('level_term_section', 'VARCHAR(100)' if dialect != 'sqlite' else 'TEXT'),
            ('clo_data', 'TEXT'),
            ('plo_mapping', 'TEXT'),
        ]
        
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                try:
                    if dialect == 'sqlite':
                        # SQLite doesn't support IF NOT EXISTS in ALTER TABLE
                        db.session.execute(text(f"ALTER TABLE course_outline ADD COLUMN {col_name} {col_type}"))
                    else:  # MySQL, PostgreSQL, etc.
                        # Check if column exists first
                        try:
                            db.session.execute(text(f"ALTER TABLE course_outline ADD COLUMN {col_name} {col_type}"))
                        except Exception as e:
                            if 'Duplicate column name' in str(e) or 'already exists' in str(e).lower():
                                print(f"- Column {col_name} already exists (skipped)")
                                continue
                            raise
                    db.session.commit()
                    print(f"✓ Added column: {col_name}")
                except Exception as e:
                    if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
                        print(f"- Column {col_name} already exists (skipped)")
                        db.session.rollback()
                    else:
                        print(f"✗ Error adding {col_name}: {e}")
                        db.session.rollback()
            else:
                print(f"- Column {col_name} already exists")
        
        print("\n✓ All new columns added successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()

