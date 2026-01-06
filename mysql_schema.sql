-- ============================================
-- MySQL Database Schema for Academic Management System
-- cPanel Deployment - Complete Schema
-- ============================================

-- Create Database (if needed)
-- CREATE DATABASE IF NOT EXISTS academic_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- USE academic_management;

-- ============================================
-- 1. USERS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(150) NOT NULL UNIQUE,
    `email` VARCHAR(120) NOT NULL UNIQUE,
    `full_name` VARCHAR(120) NOT NULL,
    `password_hash` VARCHAR(512) NOT NULL,
    `role` VARCHAR(20) NOT NULL DEFAULT 'user',
    INDEX `idx_username` (`username`),
    INDEX `idx_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 2. TEACHER TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `teacher` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `short_name` VARCHAR(10) NOT NULL UNIQUE,
    INDEX `idx_short_name` (`short_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 3. CURRICULUM TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `curriculum` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `date` VARCHAR(50) NULL,
    `applicable_batches` TEXT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 4. COURSE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `course` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `curriculum_id` INT NULL,
    `course_code` VARCHAR(20) NOT NULL,
    `course_name` VARCHAR(100) NOT NULL,
    `credit` FLOAT NOT NULL,
    `course_type` VARCHAR(50) NOT NULL,
    `category` VARCHAR(20) NOT NULL DEFAULT 'ug',
    `core_optional` VARCHAR(20) NULL,
    `syllabus_year` VARCHAR(20) NULL,
    `offered` BOOLEAN NOT NULL DEFAULT TRUE,
    `year` VARCHAR(50) NULL,
    `term` VARCHAR(50) NULL,
    `rationale` TEXT NULL,
    `clo` TEXT NULL,
    `content_section_a` TEXT NULL,
    `content_section_b` TEXT NULL,
    FOREIGN KEY (`curriculum_id`) REFERENCES `curriculum`(`id`) ON DELETE SET NULL,
    INDEX `idx_course_code` (`course_code`),
    INDEX `idx_category` (`category`),
    UNIQUE KEY `uq_curriculum_course_code` (`curriculum_id`, `course_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 5. ASSIGNED_COURSE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `assigned_course` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `teacher_id` INT NOT NULL,
    `course_id` INT NOT NULL,
    `part` VARCHAR(10) NOT NULL DEFAULT 'Full',
    FOREIGN KEY (`teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`course_id`) REFERENCES `course`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `_teacher_course_part_uc` (`teacher_id`, `course_id`, `part`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 6. ROOM TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `room` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `room_number` VARCHAR(20) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 7. ROUTINE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `routine` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `day` VARCHAR(10) NOT NULL,
    `time_slot` VARCHAR(50) NOT NULL,
    `room_number` VARCHAR(50) NOT NULL,
    `course_code` VARCHAR(20) NULL,
    `teacher_short_name` VARCHAR(50) NULL,
    `part` VARCHAR(10) NULL,
    `is_shared` BOOLEAN DEFAULT FALSE,
    `shared_with` VARCHAR(50) NULL,
    `teacher_id` INT NULL,
    FOREIGN KEY (`teacher_id`) REFERENCES `teacher`(`id`) ON DELETE SET NULL,
    UNIQUE KEY `_day_time_room_uc` (`day`, `time_slot`, `room_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 8. CLASS_SESSION TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `class_session` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `year` VARCHAR(4) NOT NULL,
    `term` VARCHAR(20) NOT NULL,
    `academic_session` VARCHAR(20) NULL,
    `course_code` VARCHAR(20) NULL,
    `course_name` VARCHAR(100) NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `teacher_id` INT NOT NULL,
    `archived` BOOLEAN DEFAULT FALSE,
    `course_type` VARCHAR(20) NOT NULL DEFAULT 'theory',
    `category` VARCHAR(20) NOT NULL DEFAULT 'ug',
    `course_scope` VARCHAR(10) NOT NULL DEFAULT 'full',
    `split_group_id` VARCHAR(36) NULL,
    FOREIGN KEY (`teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE,
    INDEX `idx_teacher_id` (`teacher_id`),
    INDEX `idx_split_group_id` (`split_group_id`),
    INDEX `idx_archived` (`archived`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 9. CLASS_STUDENT TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `class_student` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` VARCHAR(20) NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    `session_id` INT NOT NULL,
    `teacher_id` INT NOT NULL,
    `assessment1` FLOAT NULL,
    `assessment2` FLOAT NULL,
    `assessment3` FLOAT NULL,
    `assessment4` FLOAT NULL,
    `assessment_total` FLOAT NULL,
    `assessment_avg` FLOAT NULL,
    `assessment_total_40` FLOAT NULL,
    `sessional_report` FLOAT NULL,
    `sessional_viva` FLOAT NULL,
    `assessment_absent` TEXT NULL,
    FOREIGN KEY (`session_id`) REFERENCES `class_session`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE,
    INDEX `idx_session_id` (`session_id`),
    INDEX `idx_teacher_id` (`teacher_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 10. CLASS_ATTENDANCE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `class_attendance` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `date` DATE NOT NULL,
    `is_present` BOOLEAN DEFAULT FALSE,
    `student_id` INT NOT NULL,
    `session_id` INT NOT NULL,
    `teacher_id` INT NOT NULL,
    FOREIGN KEY (`student_id`) REFERENCES `class_student`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`session_id`) REFERENCES `class_session`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE,
    INDEX `idx_student_id` (`student_id`),
    INDEX `idx_session_id` (`session_id`),
    INDEX `idx_date` (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 11. CLASS_SPLIT_INVITE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `class_split_invite` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `split_group_id` VARCHAR(36) NOT NULL,
    `inviter_session_id` INT NOT NULL,
    `inviter_teacher_id` INT NOT NULL,
    `invited_teacher_id` INT NOT NULL,
    `invited_scope` VARCHAR(10) NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `responded_at` DATETIME NULL,
    FOREIGN KEY (`inviter_session_id`) REFERENCES `class_session`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`inviter_teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`invited_teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE,
    INDEX `idx_split_group_id` (`split_group_id`),
    INDEX `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 12. COURSE_REVIEW TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `course_review` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `session_id` INT NOT NULL,
    `teacher_id` INT NOT NULL,
    `data` TEXT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`session_id`) REFERENCES `class_session`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 13. EVALUATION_INVITE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `evaluation_invite` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `session_id` INT NOT NULL,
    `inviter_teacher_id` INT NOT NULL,
    `evaluator_teacher_id` INT NOT NULL,
    `status` VARCHAR(20) DEFAULT 'invited',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`session_id`) REFERENCES `class_session`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`inviter_teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`evaluator_teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE,
    INDEX `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 14. EVALUATION_SUBMISSION TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `evaluation_submission` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `invite_id` INT NOT NULL,
    `session_id` INT NOT NULL,
    `evaluator_teacher_id` INT NOT NULL,
    `general_info` TEXT NULL,
    `scores` TEXT NULL,
    `comments_observer` TEXT NULL,
    `comments_presenter` TEXT NULL,
    `total_score` INT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`invite_id`) REFERENCES `evaluation_invite`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`session_id`) REFERENCES `class_session`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`evaluator_teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 15. EXAM_PAPER_EVALUATION TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `exam_paper_evaluation` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `course_name` VARCHAR(150) NOT NULL,
    `course_code` VARCHAR(50) NOT NULL,
    `discipline` VARCHAR(100) NULL,
    `school` VARCHAR(100) NULL,
    `year` VARCHAR(10) NULL,
    `term` VARCHAR(10) NULL,
    `section` VARCHAR(50) NULL,
    `program_level` VARCHAR(20) NOT NULL,
    `archived` BOOLEAN DEFAULT FALSE,
    `marks_data` TEXT NULL,
    `owner_teacher_id` INT NULL,
    `assigned_scrutinizer_id` INT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`owner_teacher_id`) REFERENCES `teacher`(`id`) ON DELETE SET NULL,
    FOREIGN KEY (`assigned_scrutinizer_id`) REFERENCES `teacher`(`id`) ON DELETE SET NULL,
    INDEX `idx_archived` (`archived`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 16. EXAM_SCRUTINIZER_INVITE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `exam_scrutinizer_invite` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `exam_entry_id` INT NOT NULL,
    `inviter_teacher_id` INT NOT NULL,
    `scrutinizer_teacher_id` INT NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'invited',
    `remarks` TEXT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `responded_at` DATETIME NULL,
    FOREIGN KEY (`exam_entry_id`) REFERENCES `exam_paper_evaluation`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`inviter_teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`scrutinizer_teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE,
    INDEX `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 17. STUDENT_FEEDBACK_LINK TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `student_feedback_link` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `session_id` INT NOT NULL,
    `access_code` VARCHAR(32) NOT NULL UNIQUE,
    `title` VARCHAR(120) NULL,
    `description` TEXT NULL,
    `expires_at` DATETIME NULL,
    `allow_multiple` BOOLEAN DEFAULT FALSE,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`session_id`) REFERENCES `class_session`(`id`) ON DELETE CASCADE,
    INDEX `idx_access_code` (`access_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 18. STUDENT_FEEDBACK_RESPONSE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `student_feedback_response` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `feedback_link_id` INT NOT NULL,
    `payload` TEXT NOT NULL,
    `submitted_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`feedback_link_id`) REFERENCES `student_feedback_link`(`id`) ON DELETE CASCADE,
    INDEX `idx_feedback_link_id` (`feedback_link_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 19. COURSE_OUTLINE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `course_outline` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `session_id` INT NOT NULL,
    `teacher_id` INT NOT NULL,
    `course_objectives` TEXT NULL,
    `course_summary` TEXT NULL,
    `prerequisites` VARCHAR(200) NULL,
    `contact_hours` VARCHAR(50) NULL,
    `cie_marks` VARCHAR(50) NULL,
    `smee_marks` VARCHAR(50) NULL,
    `lesson_plan` TEXT NULL,
    `course_content_summary` TEXT NULL,
    `clo_plo_mapping` TEXT NULL,
    `assessment_strategy` TEXT NULL,
    `assessment_techniques` TEXT NULL,
    `rubrics` TEXT NULL,
    `grading_policy` TEXT NULL,
    `evaluation_policy` TEXT NULL,
    `cie_breakdown` TEXT NULL,
    `smee_breakdown` TEXT NULL,
    `textbooks` TEXT NULL,
    `reference_books` TEXT NULL,
    `other_resources` TEXT NULL,
    `course_file_components` TEXT NULL,
    `make_up_procedures` TEXT NULL,
    `other_issues` TEXT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`session_id`) REFERENCES `class_session`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`teacher_id`) REFERENCES `teacher`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `idx_session_outline` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 20. RESULT_SESSION TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `result_session` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `term` VARCHAR(50) NOT NULL,
    `year` VARCHAR(50) NULL,
    `batch` VARCHAR(50) NULL,
    `curriculum_id` INT NULL,
    `is_archived` BOOLEAN NOT NULL DEFAULT FALSE,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_is_archived` (`is_archived`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 21. RESULT_STUDENT TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `result_student` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` VARCHAR(50) NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    `year` VARCHAR(50) NULL,
    `discipline` VARCHAR(100) NULL,
    `school` VARCHAR(100) NULL,
    `session_id` INT NOT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`session_id`) REFERENCES `result_session`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `_student_session_uc` (`student_id`, `session_id`),
    INDEX `idx_session_id` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 22. RESULT_SUBJECT TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `result_subject` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `code` VARCHAR(50) NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    `credit` FLOAT NOT NULL,
    `subject_type` VARCHAR(20) NOT NULL,
    `dissertation_type` VARCHAR(20) NULL,
    `has_retake` BOOLEAN DEFAULT FALSE,
    `session_id` INT NOT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`session_id`) REFERENCES `result_session`(`id`) ON DELETE CASCADE,
    INDEX `idx_session_id` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 23. RESULT_MARK TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `result_mark` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `subject_id` INT NOT NULL,
    `attendance` FLOAT NULL,
    `continuous_assessment` FLOAT NULL,
    `part_a` FLOAT NULL,
    `part_b` FLOAT NULL,
    `sessional_report` FLOAT NULL,
    `sessional_viva` FLOAT NULL,
    `supervisor_assessment` FLOAT NULL,
    `proposal_presentation` FLOAT NULL,
    `project_report` FLOAT NULL,
    `defense` FLOAT NULL,
    `viva` FLOAT NULL,
    `total_marks` FLOAT NULL,
    `grade_point` FLOAT NULL,
    `grade_letter` VARCHAR(2) NULL,
    `is_retake` BOOLEAN DEFAULT FALSE,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`student_id`) REFERENCES `result_student`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`subject_id`) REFERENCES `result_subject`(`id`) ON DELETE CASCADE,
    INDEX `idx_student_id` (`student_id`),
    INDEX `idx_subject_id` (`subject_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 24. RESULT_COURSE_REGISTRATION TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `result_course_registration` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `subject_id` INT NOT NULL,
    `is_retake` BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (`student_id`) REFERENCES `result_student`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`subject_id`) REFERENCES `result_subject`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `_r_student_subject_retake_uc` (`student_id`, `subject_id`, `is_retake`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 25. STUDENT TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS `student` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` VARCHAR(50) NOT NULL UNIQUE,
    `name` VARCHAR(100) NOT NULL,
    `batch` VARCHAR(20) NULL,
    `email` VARCHAR(120) NULL,
    `phone` VARCHAR(20) NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_student_id` (`student_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 26. ALEMBIC_VERSION TABLE (for migrations)
-- ============================================
CREATE TABLE IF NOT EXISTS `alembic_version` (
    `version_num` VARCHAR(32) NOT NULL PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- END OF SCHEMA
-- ============================================


