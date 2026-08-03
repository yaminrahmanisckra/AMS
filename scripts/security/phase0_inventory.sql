-- Phase 0 inventory queries — run against production (read-only) before any auth/schema gates.
-- Save results under ams_backups/inventory_<date>/

SELECT DISTINCT role FROM users ORDER BY role;

SELECT role, COUNT(*) AS n FROM users GROUP BY role ORDER BY n DESC;

SELECT id, username, full_name, role, teacher_id
FROM users
WHERE role LIKE '%teaching_assistant%' OR role LIKE '%teaching assistant%';

SELECT t.id AS teacher_id, t.name AS teacher_name, u.id AS user_id, u.full_name, u.username, u.role, u.teacher_id
FROM teacher t
LEFT JOIN users u ON u.teacher_id = t.id OR u.full_name = t.name
WHERE u.id IS NULL
   OR (u.full_name IS NOT NULL AND u.full_name <> t.name)
   OR (u.teacher_id IS NULL AND u.full_name = t.name);

SELECT id, username, full_name, role, teacher_id
FROM users
WHERE (role LIKE '%teacher%' OR role LIKE '%head%' OR role LIKE '%dean%')
  AND teacher_id IS NULL;

SELECT id, name, is_active FROM operational_window ORDER BY id;

SELECT 'users' AS tbl, COUNT(*) AS n FROM users
UNION ALL SELECT 'r_mark', COUNT(*) FROM r_mark
UNION ALL SELECT 'class_attendance', COUNT(*) FROM class_attendance
UNION ALL SELECT 'student_course_registration', COUNT(*) FROM student_course_registration;
