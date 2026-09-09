-- AUTH-01: store reset codes server-side. Run in phpMyAdmin BEFORE deploying
-- the matching auth code. Existing signed `challenge` cookies become useless.

CREATE TABLE IF NOT EXISTS password_reset_code (
  id INT AUTO_INCREMENT PRIMARY KEY,
  request_id VARCHAR(64) NOT NULL,
  user_id INT NOT NULL,
  salt VARCHAR(64) NOT NULL,
  code_hash VARCHAR(64) NOT NULL,
  password_fingerprint VARCHAR(16) NOT NULL,
  attempts INT NOT NULL DEFAULT 0,
  expires_at DATETIME NOT NULL,
  used_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_password_reset_request (request_id),
  KEY ix_password_reset_user (user_id),
  KEY ix_password_reset_expires (expires_at),
  CONSTRAINT fk_password_reset_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
