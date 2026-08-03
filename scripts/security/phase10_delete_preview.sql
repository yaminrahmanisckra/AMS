-- Phase 10 helper: preview delete-old-data impact before running admin UI deletes.
-- Run read-only; do not DELETE from this script.

SELECT 'class_session' AS tbl, COUNT(*) AS n FROM class_session
UNION ALL SELECT 'class_attendance', COUNT(*) FROM class_attendance
UNION ALL SELECT 'student_course_registration', COUNT(*) FROM student_course_registration
UNION ALL SELECT 'r_mark', COUNT(*) FROM r_mark;

-- Confirm operational windows before any mass delete
SELECT id, name, is_active FROM operational_window ORDER BY id;
