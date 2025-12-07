-- Add missing columns to course_outline table for SQLite
-- Run this with: sqlite3 your_database.db < add_columns_sqlite.sql

ALTER TABLE course_outline ADD COLUMN course_content_summary TEXT;
ALTER TABLE course_outline ADD COLUMN clo_plo_mapping TEXT;
ALTER TABLE course_outline ADD COLUMN evaluation_policy TEXT;
ALTER TABLE course_outline ADD COLUMN cie_breakdown TEXT;
ALTER TABLE course_outline ADD COLUMN smee_breakdown TEXT;
ALTER TABLE course_outline ADD COLUMN course_file_components TEXT;

-- Add assessment_revealed column to class_session table
ALTER TABLE class_session ADD COLUMN assessment_revealed TEXT NULL;


