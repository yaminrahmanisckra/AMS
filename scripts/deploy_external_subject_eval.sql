-- External Subject Evaluation (revision m3n4o5p6q7r8)
-- Run in phpMyAdmin BEFORE or immediately after uploading code files.
-- Safe to re-run: skips if column already exists.

SET @col_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'exam_paper_evaluation'
      AND COLUMN_NAME = 'is_external_subject'
);

SET @sql = IF(
    @col_exists = 0,
    'ALTER TABLE exam_paper_evaluation ADD COLUMN is_external_subject TINYINT(1) NOT NULL DEFAULT 0',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Backfill: owner entries with no committee assignment link
UPDATE exam_paper_evaluation
SET is_external_subject = 1
WHERE owner_teacher_id IS NOT NULL
  AND id NOT IN (
    SELECT exam_paper_evaluation_id
    FROM (
        SELECT exam_paper_evaluation_id
        FROM exam_paper_evaluator_assignment
        WHERE exam_paper_evaluation_id IS NOT NULL
    ) AS linked
  );

UPDATE alembic_version SET version_num = 'm3n4o5p6q7r8';
