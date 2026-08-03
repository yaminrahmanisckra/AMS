-- Phase 3 schema widenings + Phase 9 must_change_password + login_throttle
-- Run in phpMyAdmin AFTER a verified restore-tested dump.
-- Verify each with SHOW CREATE TABLE before uploading code that depends on it.

ALTER TABLE users MODIFY COLUMN role VARCHAR(120) NOT NULL;
ALTER TABLE users ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0;

-- Course type values like 'Dissertation Proposal (PG)' need >20 chars
ALTER TABLE course MODIFY COLUMN course_type VARCHAR(40) NOT NULL;

-- Semester archives exceed TEXT (65KB)
ALTER TABLE session_archive MODIFY COLUMN archive_data LONGTEXT NOT NULL;

-- Login throttle (Phase 9) — fail-open if missing; create before wiring auth
CREATE TABLE IF NOT EXISTS login_throttle (
  id INT AUTO_INCREMENT PRIMARY KEY,
  key_hash VARCHAR(64) NOT NULL,
  fail_count INT NOT NULL DEFAULT 0,
  first_fail_at DATETIME NULL,
  locked_until DATETIME NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_login_throttle_key (key_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
