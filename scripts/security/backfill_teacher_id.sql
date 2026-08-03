-- Backfill users.teacher_id from exact Teacher.name matches (Phase 7-8 security work).
--
-- Context: several ownership checks (utils/ownership.py) prefer users.teacher_id
-- and only fall back to an exact users.full_name == teacher.name match. Many
-- existing accounts were created before users.teacher_id was consistently
-- populated, so they rely entirely on the name-match fallback. This script
-- links them explicitly, which is faster, unambiguous, and no longer breaks
-- if a name is renamed later (renames are now blocked for teaching staff,
-- see app.py /profile route, but this closes the gap for any legacy rows).
--
-- Safe by construction:
--   * Only touches users where teacher_id IS NULL (never overwrites an
--     existing, possibly intentionally different, link).
--   * Only links when the full_name matches EXACTLY one teacher row
--     (case-sensitive, trimmed). Ambiguous/ multiple matches are reported,
--     not auto-linked, so they can be resolved by hand.
--   * Read-only report queries are provided first; run them, review, THEN
--     run the UPDATE.
--
-- Run against production only after taking a fresh backup (see
-- scripts/security/phase0_checklist.md).

-- ---------------------------------------------------------------------------
-- Step 1 (read-only): Preview candidates that WILL be backfilled.
-- ---------------------------------------------------------------------------
SELECT
    u.id            AS user_id,
    u.username,
    u.full_name,
    u.role,
    t.id            AS candidate_teacher_id,
    t.name          AS candidate_teacher_name
FROM users u
JOIN teacher t
    ON TRIM(t.name) = TRIM(u.full_name)
WHERE u.teacher_id IS NULL
GROUP BY u.id
HAVING COUNT(DISTINCT t.id) = 1
ORDER BY u.id;

-- ---------------------------------------------------------------------------
-- Step 2 (read-only): Ambiguous names — more than one Teacher row shares the
-- same name as a user with no teacher_id. These need manual resolution
-- (e.g. rename/merge duplicate Teacher rows) and are intentionally excluded
-- from the automatic backfill below.
-- ---------------------------------------------------------------------------
SELECT
    u.id            AS user_id,
    u.username,
    u.full_name,
    u.role,
    COUNT(DISTINCT t.id) AS matching_teacher_count,
    GROUP_CONCAT(t.id ORDER BY t.id) AS matching_teacher_ids
FROM users u
JOIN teacher t
    ON TRIM(t.name) = TRIM(u.full_name)
WHERE u.teacher_id IS NULL
GROUP BY u.id
HAVING COUNT(DISTINCT t.id) > 1
ORDER BY u.id;

-- ---------------------------------------------------------------------------
-- Step 3 (read-only): Teaching-role users who still have no teacher_id and
-- no name match at all (need a Teacher record created/linked manually,
-- typically via the admin "Edit User" screen).
-- ---------------------------------------------------------------------------
SELECT u.id AS user_id, u.username, u.full_name, u.role
FROM users u
LEFT JOIN teacher t ON TRIM(t.name) = TRIM(u.full_name)
WHERE u.teacher_id IS NULL
  AND (u.role LIKE '%teacher%' OR u.role LIKE '%head%' OR u.role LIKE '%dean%')
  AND t.id IS NULL;

-- ---------------------------------------------------------------------------
-- Step 4 (WRITE): Backfill users.teacher_id for unambiguous exact matches.
-- Uncomment and run only after reviewing Steps 1-3 above.
-- ---------------------------------------------------------------------------
-- UPDATE users u
-- JOIN (
--     SELECT u2.id AS user_id, MIN(t.id) AS teacher_id
--     FROM users u2
--     JOIN teacher t ON TRIM(t.name) = TRIM(u2.full_name)
--     WHERE u2.teacher_id IS NULL
--     GROUP BY u2.id
--     HAVING COUNT(DISTINCT t.id) = 1
-- ) match ON match.user_id = u.id
-- SET u.teacher_id = match.teacher_id
-- WHERE u.teacher_id IS NULL;

-- ---------------------------------------------------------------------------
-- Step 5 (read-only): Verification after running Step 4.
-- ---------------------------------------------------------------------------
-- SELECT COUNT(*) AS still_unlinked_teaching_staff
-- FROM users
-- WHERE teacher_id IS NULL
--   AND (role LIKE '%teacher%' OR role LIKE '%head%' OR role LIKE '%dean%');
