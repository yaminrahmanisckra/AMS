"""Script to add missing columns to course_outline table"""
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
        existing_columns = [col['name'] for col in inspector.get_columns('course_outline')]
        print(f"Existing columns: {existing_columns}")
        
        columns_to_add = [
            ('course_content_summary', 'TEXT'),
            ('clo_plo_mapping', 'TEXT'),
            ('evaluation_policy', 'TEXT'),
            ('cie_breakdown', 'TEXT'),
            ('smee_breakdown', 'TEXT'),
            ('course_file_components', 'TEXT'),
            ('credit_value', 'VARCHAR(20)'),
            ('course_type', 'VARCHAR(50)'),
            ('level_term_section', 'VARCHAR(100)'),
            ('clo_data', 'TEXT'),
            ('plo_mapping', 'TEXT'),
        ]
        
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                try:
                    if dialect == 'sqlite':
                        db.session.execute(text(f"ALTER TABLE course_outline ADD COLUMN {col_name} {col_type}"))
                    else:  # MySQL, PostgreSQL, etc.
                        db.session.execute(text(f"ALTER TABLE course_outline ADD COLUMN {col_name} {col_type}"))
                    print(f"✓ Added column: {col_name}")
                except Exception as e:
                    print(f"✗ Error adding {col_name}: {e}")
            else:
                print(f"- Column {col_name} already exists")
        
        db.session.commit()
        print("\nAll columns added successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()

