-- Audit log (manual). Safe to re-run: CREATE TABLE IF NOT EXISTS.
-- Does not alter users, marks, or any existing tables.
-- phpMyAdmin: select the AMS database, then Import / SQL tab.

CREATE TABLE IF NOT EXISTS audit_log (
    id INT NOT NULL AUTO_INCREMENT,
    created_at DATETIME NOT NULL,
    actor_user_id INT NULL,
    actor_username VARCHAR(150) NULL,
    actor_role VARCHAR(120) NULL,
    action VARCHAR(80) NOT NULL,
    entity_type VARCHAR(40) NOT NULL,
    entity_id VARCHAR(64) NULL,
    before_json TEXT NULL,
    after_json TEXT NULL,
    extra_json TEXT NULL,
    ip VARCHAR(64) NULL,
    path VARCHAR(255) NULL,
    PRIMARY KEY (id),
    INDEX idx_audit_created (created_at),
    INDEX idx_audit_action (action),
    INDEX idx_audit_entity (entity_type, entity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
