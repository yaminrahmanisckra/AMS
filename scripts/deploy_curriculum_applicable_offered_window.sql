-- Curriculum Management: window-scoped Applicable For + Offered (revision i9j0k1l2m3n4)
-- Run in phpMyAdmin after uploading code.

CREATE TABLE IF NOT EXISTS curriculum_applicable_batch (
    id INT NOT NULL AUTO_INCREMENT,
    curriculum_id INT NOT NULL,
    window_id INT NOT NULL,
    applicable_batches TEXT NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_curriculum_applicable_batch_window (curriculum_id, window_id),
    KEY ix_curriculum_applicable_batch_window_id (window_id),
    CONSTRAINT fk_cab_curriculum FOREIGN KEY (curriculum_id) REFERENCES curriculum(id),
    CONSTRAINT fk_cab_window FOREIGN KEY (window_id) REFERENCES operational_window(id)
);

CREATE TABLE IF NOT EXISTS course_window_offered (
    id INT NOT NULL AUTO_INCREMENT,
    course_id INT NOT NULL,
    window_id INT NOT NULL,
    offered TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_course_window_offered (course_id, window_id),
    KEY ix_course_window_offered_window_id (window_id),
    CONSTRAINT fk_cwo_course FOREIGN KEY (course_id) REFERENCES course(id),
    CONSTRAINT fk_cwo_window FOREIGN KEY (window_id) REFERENCES operational_window(id)
);

INSERT INTO curriculum_applicable_batch (curriculum_id, window_id, applicable_batches, created_at, updated_at)
SELECT c.id, 1, c.applicable_batches, NOW(), NOW()
FROM curriculum c
WHERE c.applicable_batches IS NOT NULL
  AND TRIM(c.applicable_batches) != ''
  AND NOT EXISTS (
      SELECT 1 FROM curriculum_applicable_batch cab
      WHERE cab.curriculum_id = c.id AND cab.window_id = 1
  );

INSERT INTO course_window_offered (course_id, window_id, offered, created_at, updated_at)
SELECT co.id, 1, co.offered, NOW(), NOW()
FROM course co
WHERE NOT EXISTS (
    SELECT 1 FROM course_window_offered cwo
    WHERE cwo.course_id = co.id AND cwo.window_id = 1
);

UPDATE alembic_version SET version_num = 'i9j0k1l2m3n4';

-- Test checklist (Head, two windows):
-- 1. Window 1: edit curriculum Applicable For -> save -> reload -> visible
-- 2. Switch Window 2: same curriculum shows different Applicable For
-- 3. Window 1: toggle course Offered OFF -> Window 2 unchanged
-- 4. Student/coordinator registration uses window-scoped offered courses only
-- 5. Year/Term batch picker uses window-scoped Applicable For batches
