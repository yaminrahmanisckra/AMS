-- AI Course Outline Phase 3: RAG columns + batch job table (revision l2m3n4o5p6q7)

ALTER TABLE course_file_upload
    ADD COLUMN IF NOT EXISTS file_category VARCHAR(50) NULL,
    ADD COLUMN IF NOT EXISTS extracted_text TEXT NULL;

CREATE TABLE IF NOT EXISTS ai_outline_batch_job (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    academic_session VARCHAR(50) NOT NULL,
    year VARCHAR(50) NOT NULL,
    term VARCHAR(50) NOT NULL,
    batch VARCHAR(50) NULL,
    items_json TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    PRIMARY KEY (id),
    INDEX ix_ai_outline_batch_job_user_id (user_id)
);

UPDATE alembic_version SET version_num = 'l2m3n4o5p6q7';
