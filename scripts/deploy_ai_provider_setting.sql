-- AI Course Outline: ai_provider_setting table (revision j0k1l2m3n4o5)
-- Run in phpMyAdmin after uploading code.

CREATE TABLE IF NOT EXISTS ai_provider_setting (
    id INT NOT NULL AUTO_INCREMENT,
    provider VARCHAR(30) NOT NULL DEFAULT 'openai',
    display_name VARCHAR(100) NULL,
    api_key_encrypted TEXT NULL,
    model_name VARCHAR(100) NULL,
    api_base_url VARCHAR(255) NULL,
    temperature FLOAT NOT NULL DEFAULT 0.3,
    max_tokens INT NOT NULL DEFAULT 8000,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    is_default TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    PRIMARY KEY (id)
);

UPDATE alembic_version SET version_num = 'j0k1l2m3n4o5';
