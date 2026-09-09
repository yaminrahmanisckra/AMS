-- Phase 1.1 — DB-backed rate limit counters (login, reset, admission PIN, AI, PDF).
-- Safe to re-run. Does not change existing data.

CREATE TABLE IF NOT EXISTS rate_limit_bucket (
  bucket_key VARCHAR(64) NOT NULL,
  window_start DATETIME NOT NULL,
  count INT NOT NULL DEFAULT 0,
  PRIMARY KEY (bucket_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
