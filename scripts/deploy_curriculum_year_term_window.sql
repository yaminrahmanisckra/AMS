-- Curriculum Management: window-scoped curriculum_year_term (revision h8i9j0k1l2m3)
-- Run in phpMyAdmin after uploading code. If DROP INDEX fails with #1553, drop FK first.

ALTER TABLE curriculum_year_term
  ADD COLUMN window_id INT NULL,
  ADD INDEX ix_curriculum_year_term_window_id (window_id),
  ADD CONSTRAINT fk_curriculum_year_term_window
    FOREIGN KEY (window_id) REFERENCES operational_window(id);

UPDATE curriculum_year_term SET window_id = 1 WHERE window_id IS NULL;

-- If #1553: ALTER TABLE curriculum_year_term DROP FOREIGN KEY fk_curriculum_year_term_curriculum; (name may vary)
ALTER TABLE curriculum_year_term DROP INDEX uq_curriculum_year_term_session;

ALTER TABLE curriculum_year_term
  ADD UNIQUE KEY uq_curriculum_year_term_window_session
  (window_id, curriculum_id, year, term, academic_session);

UPDATE alembic_version SET version_num = 'h8i9j0k1l2m3';

-- Test checklist (Head, two windows):
-- 1. Window 1: set Year/Term session+batch → save → reload → visible
-- 2. Switch Window 2: same curriculum shows empty config
-- 3. Window 2: different session/batch does not overwrite Window 1
-- 4. Assign teacher in Window 2 → course_session_assignment.window_id = 2
-- 5. Clear assignments clears active window only
-- 6. Course Registration dropdowns use window-scoped batches/sessions
-- 7. Curriculator unchanged (global)
