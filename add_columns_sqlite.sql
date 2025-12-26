-- Add missing columns to course_outline table for SQLite
-- Run this with: sqlite3 your_database.db < add_columns_sqlite.sql

-- Existing columns (if not already added)
ALTER TABLE course_outline ADD COLUMN course_content_summary TEXT;
ALTER TABLE course_outline ADD COLUMN clo_plo_mapping TEXT;
ALTER TABLE course_outline ADD COLUMN evaluation_policy TEXT;
ALTER TABLE course_outline ADD COLUMN cie_breakdown TEXT;
ALTER TABLE course_outline ADD COLUMN smee_breakdown TEXT;
ALTER TABLE course_outline ADD COLUMN course_file_components TEXT;

-- New columns for PDF structure
ALTER TABLE course_outline ADD COLUMN credit_value VARCHAR(20);
ALTER TABLE course_outline ADD COLUMN course_type VARCHAR(50);
ALTER TABLE course_outline ADD COLUMN level_term_section VARCHAR(100);
ALTER TABLE course_outline ADD COLUMN clo_data TEXT;
ALTER TABLE course_outline ADD COLUMN plo_mapping TEXT;

-- Add assessment_revealed column to class_session table
ALTER TABLE class_session ADD COLUMN assessment_revealed TEXT NULL;


