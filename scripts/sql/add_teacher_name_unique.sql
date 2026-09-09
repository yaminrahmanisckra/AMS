-- AUTHZ-07 / Phase 1.4: enforce unique Teacher.name
--
-- Run AFTER confirming no duplicate names (Step 1).
-- Safe: only adds a unique index; does not delete or rewrite rows.

-- Step 1 (read-only): duplicate Teacher names (must be empty before Step 2)
SELECT TRIM(name) AS teacher_name, COUNT(*) AS cnt, GROUP_CONCAT(id ORDER BY id) AS teacher_ids
FROM teacher
GROUP BY TRIM(name)
HAVING COUNT(*) > 1
ORDER BY cnt DESC, teacher_name;

-- Step 2 (WRITE): unique index on teacher.name
-- MySQL / MariaDB:
ALTER TABLE teacher
  ADD UNIQUE INDEX uq_teacher_name (name);

-- If Step 2 fails with "Duplicate entry", fix Step 1 duplicates first
-- (rename or merge Teacher rows), then retry.
