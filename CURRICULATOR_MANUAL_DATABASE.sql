-- ============================================================
-- Curriculator মডিউল — ম্যানুয়াল ডাটাবেজ সেটআপ (MySQL/MariaDB)
-- phpMyAdmin এ ইমপোর্ট করুন অথবা একটার পর একটা কুয়েরি চালান।
-- ক্রম মানতে হবে: যে টেবিলের উপর FK আছে সে টেবিল আগে থাকতে হবে।
-- আগে থেকেই থাকা দরকার: users, course, teacher
-- ============================================================

-- 1. syllabus_document
CREATE TABLE IF NOT EXISTS syllabus_document (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(200) NOT NULL,
    applicable_batches TEXT,
    source_file VARCHAR(500),
    created_at DATETIME DEFAULT NULL,
    updated_at DATETIME DEFAULT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. syllabus_part (FK: syllabus_document)
CREATE TABLE IF NOT EXISTS syllabus_part (
    id INT NOT NULL AUTO_INCREMENT,
    document_id INT NOT NULL,
    part_key VARCHAR(10) NOT NULL,
    title VARCHAR(200) DEFAULT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    content TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT NULL,
    updated_at DATETIME DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_syllabus_part_doc_key (document_id, part_key),
    CONSTRAINT fk_syllabus_part_document FOREIGN KEY (document_id) REFERENCES syllabus_document (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. syllabus_course_entry (FK: syllabus_part, course)
CREATE TABLE IF NOT EXISTS syllabus_course_entry (
    id INT NOT NULL AUTO_INCREMENT,
    part_id INT NOT NULL,
    course_id INT DEFAULT NULL,
    course_code VARCHAR(50) DEFAULT NULL,
    course_name VARCHAR(200) DEFAULT NULL,
    credit FLOAT DEFAULT NULL,
    year_term VARCHAR(100) DEFAULT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    content_json TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT NULL,
    updated_at DATETIME DEFAULT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_syllabus_course_entry_part FOREIGN KEY (part_id) REFERENCES syllabus_part (id) ON DELETE CASCADE,
    CONSTRAINT fk_syllabus_course_entry_course FOREIGN KEY (course_id) REFERENCES course (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. syllabus_course_entry এ অতিরিক্ত কলাম (year, term, entry_type, status, prerequisite_entry_id)
-- টেবিল ৩ নম্বরে তৈরি হলে এরপর একটার পর একটা চালান। কোনো কলাম আগে থাকলে "Duplicate column" আসবে — ওই লাইন বাদ দিন।
ALTER TABLE syllabus_course_entry ADD COLUMN year VARCHAR(50) DEFAULT NULL;
ALTER TABLE syllabus_course_entry ADD COLUMN term VARCHAR(50) DEFAULT NULL;
ALTER TABLE syllabus_course_entry ADD COLUMN entry_type VARCHAR(30) DEFAULT NULL;
ALTER TABLE syllabus_course_entry ADD COLUMN status VARCHAR(30) DEFAULT NULL;
ALTER TABLE syllabus_course_entry ADD COLUMN prerequisite_entry_id INT DEFAULT NULL;

-- prerequisite FK (একবারই চালান; আগে থাকলে "Duplicate foreign key" আসবে — বাদ দিন)
ALTER TABLE syllabus_course_entry
    ADD CONSTRAINT fk_syllabus_course_entry_prerequisite
    FOREIGN KEY (prerequisite_entry_id) REFERENCES syllabus_course_entry (id) ON DELETE SET NULL;

-- 5. curriculator_editor (FK: users)
CREATE TABLE IF NOT EXISTS curriculator_editor (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    created_at DATETIME DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY user_id (user_id),
    CONSTRAINT fk_curriculator_editor_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. syllabus_author_assignment (FK: syllabus_course_entry, teacher, users)
CREATE TABLE IF NOT EXISTS syllabus_author_assignment (
    id INT NOT NULL AUTO_INCREMENT,
    course_entry_id INT NOT NULL,
    teacher_id INT NOT NULL,
    assigned_by_id INT DEFAULT NULL,
    created_at DATETIME DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_syllabus_author_entry_teacher (course_entry_id, teacher_id),
    CONSTRAINT fk_syllabus_author_entry FOREIGN KEY (course_entry_id) REFERENCES syllabus_course_entry (id) ON DELETE CASCADE,
    CONSTRAINT fk_syllabus_author_teacher FOREIGN KEY (teacher_id) REFERENCES teacher (id) ON DELETE CASCADE,
    CONSTRAINT fk_syllabus_author_assigned_by FOREIGN KEY (assigned_by_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. syllabus_part_a_section (FK: syllabus_part)
CREATE TABLE IF NOT EXISTS syllabus_part_a_section (
    id INT NOT NULL AUTO_INCREMENT,
    part_id INT NOT NULL,
    section_key VARCHAR(80) NOT NULL,
    data TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT NULL,
    updated_at DATETIME DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_part_a_section_part_key (part_id, section_key),
    CONSTRAINT fk_part_a_section_part FOREIGN KEY (part_id) REFERENCES syllabus_part (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. syllabus_part_b_config (FK: syllabus_part)
CREATE TABLE IF NOT EXISTS syllabus_part_b_config (
    id INT NOT NULL AUTO_INCREMENT,
    part_id INT NOT NULL,
    config_json TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT NULL,
    updated_at DATETIME DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY part_id (part_id),
    CONSTRAINT fk_part_b_config_part FOREIGN KEY (part_id) REFERENCES syllabus_part (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. syllabus_part_d_section (FK: syllabus_part)
CREATE TABLE IF NOT EXISTS syllabus_part_d_section (
    id INT NOT NULL AUTO_INCREMENT,
    part_id INT NOT NULL,
    section_key VARCHAR(80) NOT NULL,
    data TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT NULL,
    updated_at DATETIME DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_part_d_section_part_key (part_id, section_key),
    CONSTRAINT fk_part_d_section_part FOREIGN KEY (part_id) REFERENCES syllabus_part (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. syllabus_section_assignment (FK: syllabus_part, users)
CREATE TABLE IF NOT EXISTS syllabus_section_assignment (
    id INT NOT NULL AUTO_INCREMENT,
    part_id INT NOT NULL,
    section_key VARCHAR(80) NOT NULL,
    user_id INT NOT NULL,
    assigned_by_id INT DEFAULT NULL,
    created_at DATETIME DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_section_assignment_part_key (part_id, section_key),
    CONSTRAINT fk_section_assignment_part FOREIGN KEY (part_id) REFERENCES syllabus_part (id) ON DELETE CASCADE,
    CONSTRAINT fk_section_assignment_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_section_assignment_assigned_by FOREIGN KEY (assigned_by_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- শেষ। টেবিলগুলো তৈরি হওয়ার পর Curriculator মডিউল চালু করতে পারবেন।
-- ============================================================
