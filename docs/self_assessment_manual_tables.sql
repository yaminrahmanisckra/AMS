-- ============================================================
-- Self Assessment: ম্যানুয়ালি টেবিল তৈরি (MySQL)
-- ============================================================
-- ব্যবহার: যে ডাটাবেজে teacher টেবিল আছে সেটা সিলেক্ট করে
--         phpMyAdmin > SQL ট্যাবে এই স্ক্রিপ্ট পেস্ট করে Run করুন।
--         অথবা MySQL কনসোলে: USE your_database; তারপর এই ফাইল চালান।
-- ============================================================

-- 1. psac_committee
CREATE TABLE IF NOT EXISTS psac_committee (
    id INT NOT NULL AUTO_INCREMENT,
    head_teacher_id INT NOT NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (head_teacher_id) REFERENCES teacher(id)
);

-- 2. psac_committee_member
CREATE TABLE IF NOT EXISTS psac_committee_member (
    id INT NOT NULL AUTO_INCREMENT,
    committee_id INT NOT NULL,
    teacher_id INT NOT NULL,
    is_adhoc TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_psac_committee_member (committee_id, teacher_id),
    FOREIGN KEY (committee_id) REFERENCES psac_committee(id),
    FOREIGN KEY (teacher_id) REFERENCES teacher(id)
);

-- 3. survey_link
CREATE TABLE IF NOT EXISTS survey_link (
    id INT NOT NULL AUTO_INCREMENT,
    survey_type VARCHAR(32) NOT NULL,
    access_code VARCHAR(64) NOT NULL,
    title VARCHAR(200) NULL,
    committee_id INT NULL,
    created_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_survey_link_access_code (access_code),
    FOREIGN KEY (committee_id) REFERENCES psac_committee(id)
);

-- 4. survey_response
CREATE TABLE IF NOT EXISTS survey_response (
    id INT NOT NULL AUTO_INCREMENT,
    survey_type VARCHAR(32) NOT NULL,
    survey_link_id INT NOT NULL,
    payload TEXT NULL,
    ip_address VARCHAR(50) NULL,
    created_at DATETIME NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (survey_link_id) REFERENCES survey_link(id)
);

-- 5. alumni_survey_response
CREATE TABLE IF NOT EXISTS alumni_survey_response (
    id INT NOT NULL AUTO_INCREMENT,
    survey_link_id INT NULL,
    name VARCHAR(100) NULL,
    batch VARCHAR(50) NULL,
    graduation_year VARCHAR(20) NULL,
    degree_completed JSON NULL,
    current_designation VARCHAR(100) NULL,
    organization VARCHAR(150) NULL,
    employment_sector VARCHAR(100) NULL,
    employment_sector_other VARCHAR(100) NULL,
    is_enrolled TINYINT(1) NULL,
    enrollment_time VARCHAR(50) NULL,
    curriculum_balance INT NULL,
    knowledge_skills INT NULL,
    critical_thinking INT NULL,
    ethical_values INT NULL,
    gen_ed_usefulness INT NULL,
    assessment_methods INT NULL,
    moot_court INT NULL,
    library_resources INT NULL,
    faculty_support INT NULL,
    career_counseling INT NULL,
    academic_calendar INT NULL,
    admin_staff INT NULL,
    time_to_first_job VARCHAR(50) NULL,
    job_market_competitiveness VARCHAR(50) NULL,
    skills_acquired JSON NULL,
    beneficial_course_activity TEXT NULL,
    alumni_association_member TINYINT(1) NULL,
    contributions JSON NULL,
    curriculum_suggestions TEXT NULL,
    other_comments TEXT NULL,
    created_at DATETIME NULL,
    ip_address VARCHAR(50) NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (survey_link_id) REFERENCES survey_link(id)
);
