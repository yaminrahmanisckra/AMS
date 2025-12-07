# MySQL Database Schema Guide for cPanel Deployment

এই গাইডে Academic Management System-এর জন্য MySQL database-এ প্রয়োজনীয় সব tables এবং columns-এর সম্পূর্ণ তালিকা দেওয়া আছে।

## 📋 Database Tables Summary

মোট **26টি table** আছে:

### Core Tables (6)
1. `users` - User authentication and authorization
2. `teacher` - Teacher information
3. `curriculum` - Curriculum management
4. `course` - Course information
5. `assigned_course` - Teacher-course assignments
6. `room` - Room information

### Class Management Tables (9)
7. `class_session` - Class sessions
8. `class_student` - Students in classes
9. `class_attendance` - Attendance records
10. `class_split_invite` - Course split invitations
11. `course_review` - Course review data
12. `evaluation_invite` - Evaluation invitations
13. `evaluation_submission` - Evaluation submissions
14. `student_feedback_link` - Student feedback links
15. `student_feedback_response` - Student feedback responses

### Course Outline Table (1)
16. `course_outline` - Course outline and lesson plans

### Exam Management Tables (2)
17. `exam_paper_evaluation` - Exam paper evaluations
18. `exam_scrutinizer_invite` - Scrutinizer invitations

### Result Management Tables (5)
19. `result_session` - Result sessions
20. `result_student` - Students in result sessions
21. `result_subject` - Subjects in result sessions
22. `result_mark` - Marks for students
23. `result_course_registration` - Course registrations

### Routine Management Table (1)
24. `routine` - Class routine/schedule

### Student Management Table (1)
25. `student` - Student master data

### Migration Table (1)
26. `alembic_version` - Database migration tracking

---

## 🚀 cPanel-এ Database Setup করার Steps

### Step 1: Database তৈরি করুন
1. cPanel-এ যান
2. **MySQL Databases** section-এ যান
3. নতুন database তৈরি করুন (যেমন: `academic_ams`)
4. Database user তৈরি করুন এবং database-এ access দিন

### Step 2: SQL File Import করুন
1. `mysql_schema.sql` file-টি cPanel-এ upload করুন
2. **phpMyAdmin**-এ যান
3. আপনার database select করুন
4. **Import** tab-এ যান
5. `mysql_schema.sql` file select করুন
6. **Go** button click করুন

### Step 3: Environment Variables Setup করুন
`.env` file-এ নিচের variables set করুন:

```env
DATABASE_URL=mysql+pymysql://username:password@localhost/database_name
# অথবা
MYSQL_USER=your_username
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=academic_ams
MYSQL_HOST=localhost
USE_SQLITE_LOCAL=false
```

### Step 4: Verify Tables
phpMyAdmin-এ গিয়ে verify করুন যে সব 26টি table তৈরি হয়েছে।

---

## 📊 Important Columns Reference

### `class_session` Table - Key Columns
- `course_scope` (VARCHAR(10), DEFAULT 'full') - **IMPORTANT**: full | part_a | part_b
- `split_group_id` (VARCHAR(36)) - For split courses
- `category` (VARCHAR(20), DEFAULT 'ug') - ug | pg

### `class_student` Table - Key Columns
- `assessment_absent` (TEXT) - JSON format for absent status
- `assessment1`, `assessment2`, `assessment3`, `assessment4` (FLOAT)
- `sessional_report`, `sessional_viva` (FLOAT)

### `course_outline` Table - Key Columns
- `course_content_summary` (TEXT) - Part C content
- `clo_plo_mapping` (TEXT) - CLO-PLO mapping
- `evaluation_policy` (TEXT) - Evaluation policy
- `cie_breakdown` (TEXT) - CIE breakdown
- `smee_breakdown` (TEXT) - SMEE breakdown
- `course_file_components` (TEXT) - Course file components list

### `course` Table - Key Columns
- `clo` (TEXT) - Course Learning Outcomes (JSON)
- `content_section_a` (TEXT) - Section A content
- `content_section_b` (TEXT) - Section B content
- `offered` (BOOLEAN) - Whether course is currently offered

---

## ⚠️ Important Notes

1. **Character Set**: সব tables `utf8mb4` character set ব্যবহার করে (Bengali text support-এর জন্য)

2. **Foreign Keys**: সব foreign key relationships properly set করা আছে

3. **Indexes**: Performance-এর জন্য important columns-এ indexes দেওয়া আছে

4. **JSON Fields**: কিছু fields (যেমন `clo`, `lesson_plan`, `assessment_absent`) JSON format-এ data store করে

5. **Default Values**: Important fields-এ default values set করা আছে

6. **Cascade Deletes**: Related records automatically delete হবে parent record delete হলে

---

## 🔍 Verification Checklist

Database setup-এর পর verify করুন:

- [ ] সব 26টি table তৈরি হয়েছে
- [ ] `class_session` table-এ `course_scope` এবং `split_group_id` columns আছে
- [ ] `class_student` table-এ `assessment_absent` column আছে
- [ ] `course_outline` table-এ সব নতুন columns আছে:
  - [ ] `course_content_summary`
  - [ ] `clo_plo_mapping`
  - [ ] `evaluation_policy`
  - [ ] `cie_breakdown`
  - [ ] `smee_breakdown`
  - [ ] `course_file_components`
- [ ] Foreign keys properly set করা আছে
- [ ] Indexes তৈরি হয়েছে
- [ ] Character set `utf8mb4` set করা আছে

---

## 📝 Additional Notes

- যদি কোনো table missing থাকে, `mysql_schema.sql` file-টি আবার import করুন
- যদি কোনো column missing থাকে, manual ALTER TABLE statement run করুন
- Production environment-এ database backup নিয়মিত নিন

---

**Created for Academic Management System v2.0.0**


