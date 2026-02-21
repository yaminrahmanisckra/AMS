-- ম্যানুয়ালি চালান: cPanel → phpMyAdmin → আপনার ডাটাবেস সিলেক্ট → SQL ট্যাব
-- নিচের দুটো লাইন এক এক করে পেস্ট করে "Go" চাপুন। কোনটায় "Duplicate column" এলে সেটা আগে থেকেই আছে, পরেরটা চালান।

ALTER TABLE routine ADD COLUMN is_custom TINYINT(1) DEFAULT 0;
ALTER TABLE routine ADD COLUMN custom_course_name VARCHAR(200) NULL;
