-- AI Course Outline Phase 2: job + generation log tables (revision k1l2m3n4o5p6)
-- Run in phpMyAdmin after uploading code.

CREATE TABLE IF NOT EXISTS ai_outline_generation_job (
    id INT NOT NULL AUTO_INCREMENT,
    session_id INT NOT NULL,
    user_id INT NOT NULL,
    teacher_id INT NULL,
    parts_json TEXT NOT NULL,
    part_index INT NOT NULL DEFAULT 0,
    partial_payload_json TEXT NULL,
    context_summary_json TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    PRIMARY KEY (id),
    INDEX ix_ai_outline_generation_job_session_id (session_id),
    INDEX ix_ai_outline_generation_job_user_id (user_id)
);

CREATE TABLE IF NOT EXISTS ai_outline_generation_log (
    id INT NOT NULL AUTO_INCREMENT,
    job_id INT NULL,
    session_id INT NOT NULL,
    user_id INT NOT NULL,
    part VARCHAR(10) NOT NULL DEFAULT 'full',
    provider VARCHAR(30) NULL,
    model_name VARCHAR(100) NULL,
    prompt_tokens INT NULL,
    completion_tokens INT NULL,
    total_tokens INT NULL,
    estimated_cost_usd FLOAT NULL,
    duration_ms INT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'success',
    error_message TEXT NULL,
    created_at DATETIME NULL,
    PRIMARY KEY (id),
    INDEX ix_ai_outline_generation_log_job_id (job_id),
    INDEX ix_ai_outline_generation_log_session_id (session_id),
    INDEX ix_ai_outline_generation_log_user_id (user_id),
    CONSTRAINT fk_ai_outline_log_job FOREIGN KEY (job_id) REFERENCES ai_outline_generation_job(id)
);

UPDATE alembic_version SET version_num = 'k1l2m3n4o5p6';
