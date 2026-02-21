# Self Assessment – সিপ্যানেলে আপলোড ও ম্যানুয়াল ডাটাবেজ

Self Assessment মডিউল সিপ্যানেলে তুলতে **কি কি ফাইল** তুলতে হবে তার পূর্ণ তালিকা নিচে দেওয়া হলো। ডাটাবেজ টেবিল ম্যানুয়ালি তৈরি করার SQL ও ধাপও আছে।

---

## সিপ্যানেলে তুলতে হবে এমন ফাইলের পূর্ণ তালিকা

দুইটা পরিস্থিতি:

### পরিস্থিতি ১: পুরো অ্যাপ ইতিমধ্যে সিপ্যানেলে আছে (শুধু Self Assessment যোগ/আপডেট)

এই ফাইল/ফোল্ডারগুলো **অবশ্যই** আপলোড করুন:

| নং | ফাইল/ফোল্ডার | কারণ |
|----|----------------|------|
| 1 | **app.py** | Self Assessment ব্লুপ্রিন্ট রেজিস্টার আছে এমন আপডেটেড সংস্করণ (নইলে ড্যাশবোর্ডে লিংক/৫০০ আসবে) |
| 2 | **blueprints/self_assessment/** (পুরো ফোল্ডার) | মডিউল নিজে – নিচের সব কিছু এর ভেতর |

**blueprints/self_assessment/** এর ভেতর যা থাকতে হবে:
- `__init__.py` – **অবশ্যই** এই বিষয়বস্তু থাকতে হবে (নইলে `cannot import name 'self_assessment_bp'` আসবে):
  ```python
  from flask import Blueprint

  self_assessment_bp = Blueprint('self_assessment', __name__, template_folder='templates')

  from . import routes
  ```
- `models.py`
- `routes.py`
- `templates/self_assessment/` ফোল্ডার এবং এর ভেতর **সব** `.html` ফাইল (index, psac_committee, alumni/employer/student/faculty/non_academic survey ও form/response PDF, generic, response_view, responses_list ইত্যাদি)

বাকি অ্যাপ (extensions, user_models, role_utils, auth, class_management, base.html, static ইত্যাদি) ইতিমধ্যে সিপ্যানেলে থাকলে **শুধু উপরের দুটো** (app.py + blueprints/self_assessment/) আপলোড/আপডেট করলেই Self Assessment চালু হবে।

---

#### চেকলিস্ট: পূর্ণ অ্যাপ আছে, শুধু Self Assessment যুক্ত করব

1. **সিপ্যানেল ফাইল ম্যানেজারে আপলোড করুন**
   - **app.py** (প্রজেক্টের রুট থেকে – যেখানে `from blueprints.self_assessment import self_assessment_bp` ও `app.register_blueprint(self_assessment_bp, url_prefix='/self-assessment')` আছে)
   - **blueprints/self_assessment/** – পুরো ফোল্ডার (ভেতরে `__init__.py`, `models.py`, `routes.py`, `templates/self_assessment/` ও তার সব `.html`)

2. **ডাটাবেজে টেবিল তৈরি করুন**  
   নিচের **“২. ম্যানুয়ালি ডাটাবেজে টেবিল এন্ট্রি (SQL)”** সেকশনের SQL দিয়ে এই পাঁচটা টেবিল ক্রিয়েট করুন (অর্ডার মেনে):  
   `psac_committee` → `psac_committee_member` → `survey_link` → `survey_response` → `alumni_survey_response`  
   (ডাটাবেজে `teacher` টেবিল আগে থেকেই থাকতে হবে।)

3. **অ্যাপ রিস্টার্ট করুন**  
   সিপ্যানেলের Python অ্যাপ থেকে অ্যাপ রিস্টার্ট দিন।

4. **টেস্ট করুন**
   - লগইন করে Head/Dean ড্যাশবোর্ডে **Self Assessment** কার্ড ক্লিক করুন → `/self-assessment` ওঠা উচিত।
   - PSAC Committee সেটআপ করুন, সার্ভে লিংক জেনারেট করুন এবং একটা টেস্ট রেসপন্স সাবমিট করুন।

---

#### আপলোডের পর ৫০০ (Internal Server Error) দেখালে

১. **সিপ্যানেলে Error Log দেখুন**  
   cPanel → Errors বা Python App এর log ফাইলে আসল এরর মেসেজ থাকবে (যেমন `Table 'xxx.psac_committee' doesn't exist` বা কোন মডিউল নেই)।

২. **ডাটাবেজে টেবিল আছে কিনা নিশ্চিত করুন**  
   অনেক সময় ৫০০ আসে শুধু **পাঁচটা টেবিল** না থাকার জন্য। একই ডাটাবেজে নিচের টেবিলগুলো থাকতে হবে (নিচের “২. ম্যানুয়ালি ডাটাবেজে টেবিল এন্ট্রি” দিয়ে তৈরি করুন):  
   `psac_committee`, `psac_committee_member`, `survey_link`, `survey_response`, `alumni_survey_response`।  
   `teacher` টেবিল আগে থেকেই থাকতে হবে।

৩. **অ্যাপ রেজিলিয়েন্ট করা আছে**  
   এখন `app.py` এ Self Assessment ব্লুপ্রিন্ট লোড করার সময় কোনো এক্সেপশন হলে অ্যাপ ক্র্যাশ করবে না, বাকি সাইট চালু থাকবে। তাই ইমপোর্ট/মডিউল এরর থাকলে লগে দেখবেন, সাইট ৫০০ দেবে না।

---

### পরিস্থিতি ২: নতুন সাইট বা শুধু Self Assessment চালাতে (অ্যাপের বাকি অংশ নেই)

এই ক্ষেত্রে Self Assessment চালানোর জন্য **নিচের সব** ফাইল/ফোল্ডার আপলোড করতে হবে:

| নং | ফাইল/ফোল্ডার | কারণ |
|----|----------------|------|
| 1 | **app.py** | অ্যাপ এন্ট্রি; self_assessment ব্লুপ্রিন্ট রেজিস্টার থাকতে হবে |
| 2 | **extensions.py** | DB, Mail – অ্যাপ ব্যবহার করে |
| 3 | **user_models.py** | User মডেল – লগইনের জন্য |
| 4 | **role_utils.py** | parse_roles ইত্যাদি – Self Assessment রাউট ব্যবহার করে |
| 5 | **error_handler.py** | অ্যাপ ইমপোর্ট করে থাকলে দরকার |
| 6 | **blueprints/auth/** (পুরো ফোল্ডার) | লগইন পেজ ও লগইন লজিক |
| 7 | **blueprints/class_management/models.py** | Teacher মডেল – PSAC কমিটি হেড/মেম্বার এর জন্য (Self Assessment এর উপর নির্ভর) |
| 8 | **blueprints/self_assessment/** (পুরো ফোল্ডার) | Self Assessment মডিউল |
| 9 | **templates/base.html** | সব Self Assessment পেজ `extends "base.html"` করে |
| 10 | **templates/auth/login.html** (ও লগইন সংক্রান্ত অন্য টেমপ্লেট) | লগইন পেজ |
| 11 | **static/** (প্রয়োজনীয় অংশ) | base.html এ CSS/JS; পিডিএফে বাংলা ফন্ট চাইলে `static/Fonts/` বা `static/fonts/` এ kalpurush (ঐচ্ছিক) |
| 12 | **requirements.txt** | পাইথন প্যাকেজ তালিকা (WeasyPrint, PyPDF2, Flask ইত্যাদি) |

ডাটাবেজে **users** ও **teacher** টেবিল থাকতে হবে (লগইন ও PSAC কমিটি এর জন্য); তারপর নিচের SQL দিয়ে Self Assessment এর পাঁচটা টেবিল ম্যানুয়ালি তৈরি করুন।

---

## অ্যাপ এন্ট্রি: পুরো অ্যাপ নাকি শুধু Self Assessment

দুইভাবে ডিপ্লয় করতে পারবেন:

| পদ্ধতি | কখন ব্যবহার করবেন | অ্যাপ ফাইল |
|--------|---------------------|-------------|
| **পুরো অ্যাপ** | ইতিমধ্যে পুরো Academic Management অ্যাপ সিপ্যানেলে আছে, শুধু Self Assessment যোগ/আপডেট করছেন | `app.py` (আপডেটেড, যেখানে self_assessment ব্লুপ্রিন্ট রেজিস্টার আছে) |
| **শুধু Self Assessment** | নতুন সাইটে শুধু Self Assessment মডিউল চালাতে চান (লগইন + সার্ভে) | **`app_self_assessment.py`** |

**শুধু Self Assessment চালাতে চাইলে:** সিপ্যানেলের Python অ্যাপ সেটিংসে **Application startup file** / **Application entry point** এ লিখুন: `app_self_assessment:app` (অথবা `app_self_assessment:create_app` যদি সিপ্যানেল `create_app()` সাপোর্ট করে)।  
এ ক্ষেত্রে নিচের ফাইলগুলো অবশ্যই আপলোড করুন:
- `app_self_assessment.py`
- `extensions.py`
- `user_models.py`
- `role_utils.py`
- `blueprints/auth/` (পুরো ফোল্ডার – লগইনের জন্য)
- `blueprints/class_management/models.py` (Teacher টেবিলের জন্য – Self Assessment এর কমিটি হেড/মেম্বার)
- `blueprints/self_assessment/` (পুরো ফোল্ডার)
- `templates/base.html` এবং লগইন পেজের জন্য প্রয়োজনীয় টেমপ্লেট (যেমন `templates/auth/login.html`)

ডাটাবেজে অবশ্যই `users` ও `teacher` টেবিল থাকতে হবে (লগইন ও PSAC কমিটি এর জন্য)।

---

## ১. কি কি ফাইল তুলতে হবে (শুধু Self Assessment)

নিচের ফোল্ডার ও ফাইলগুলো **অবশ্যই** আপলোড করুন। বাকি অ্যাপ (app.py, অন্য ব্লুপ্রিন্ট, templates/base.html ইত্যাদি) ইতিমধ্যে সিপ্যানেলে থাকলে শুধু এই অংশটা যোগ/আপডেট করলেই হয়।

### ফোল্ডার: `blueprints/self_assessment/`

| যা তুলবেন | বর্ণনা |
|-----------|--------|
| **blueprints/self_assessment/__init__.py** | ব্লুপ্রিন্ট রেজিস্ট্রেশন |
| **blueprints/self_assessment/models.py** | মডেল (PsacCommittee, SurveyLink, SurveyResponse, AlumniSurveyResponse) |
| **blueprints/self_assessment/routes.py** | সব রাউট (পাবলিক ফরম, সাবমিট, পিডিএফ, অ্যাডমিন রেসপন্স) |
| **blueprints/self_assessment/templates/self_assessment/** | নিচের সব HTML ফাইল |

### টেমপ্লেট ফাইল (সবগুলো একসাথে তুলুন)

- `index.html`
- `psac_committee.html`
- `alumni_survey.html`, `alumni_survey_success.html`
- `employer_survey.html`, `student_survey.html`, `faculty_survey.html`, `non_academic_survey.html`
- `survey_placeholder.html`, `survey_success.html`, `survey_invalid.html`, `survey_already_submitted.html`
- `alumni_form_pdf.html`, `alumni_response_pdf.html`, `alumni_all_responses_pdf.html`
- `employer_form_pdf.html`, `employer_response_pdf.html`
- `student_form_pdf.html`, `student_response_pdf.html`
- `faculty_form_pdf.html`, `faculty_response_pdf.html`
- `non_academic_form_pdf.html`, `non_academic_response_pdf.html`
- `generic_form_pdf.html`, `generic_response_pdf.html`, `generic_all_responses_pdf.html`
- `response_view.html`, `response_view_employer.html`, `response_view_student.html`, `response_view_faculty.html`, `response_view_non_academic.html`
- `responses_list.html`

**সংক্ষেপ:** পুরো **`blueprints/self_assessment/`** ফোল্ডার (ভেতরে `__init__.py`, `models.py`, `routes.py` এবং **templates/self_assessment/** এর ভেতর সব `.html`) তুললেই Self Assessment এর সবকিছু আপলোড হবে।  
(অ্যাপ চালানোর জন্য রুটে `app.py`, `extensions.py`, `user_models.py`, `role_utils.py` এবং অন্য ব্লুপ্রিন্টগুলো ইতিমধ্যে থাকতে হবে।)

---

## ২. ম্যানুয়ালি ডাটাবেজে টেবিল এন্ট্রি (SQL)

নিচের স্ক্রিপ্ট **MySQL** এর জন্য। ফরেন কী এর কারণে `teacher` টেবিল আগে থাকতে হবে। যে অর্ডারে টেবিল তৈরি হবে সেটা মেনে একের পর এক চালান।

### ধাপ ১: `psac_committee`

```sql
CREATE TABLE psac_committee (
    id INT NOT NULL AUTO_INCREMENT,
    head_teacher_id INT NOT NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (head_teacher_id) REFERENCES teacher(id)
);
```

### ধাপ ২: `psac_committee_member`

```sql
CREATE TABLE psac_committee_member (
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
```

### ধাপ ৩: `survey_link`

```sql
CREATE TABLE survey_link (
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
```

### ধাপ ৪: `survey_response`

```sql
CREATE TABLE survey_response (
    id INT NOT NULL AUTO_INCREMENT,
    survey_type VARCHAR(32) NOT NULL,
    survey_link_id INT NOT NULL,
    payload TEXT NULL,
    ip_address VARCHAR(50) NULL,
    created_at DATETIME NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (survey_link_id) REFERENCES survey_link(id)
);
```

### ধাপ ৫: `alumni_survey_response` (সব কলাম একসাথে, Part D সহ)

```sql
CREATE TABLE alumni_survey_response (
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
```

**নোট:** মডেলে কলামের নাম `contribute_to_discipline` কিন্তু ডাটাবেজে কলামের নাম **`contributions`** (মডেলে `db.Column('contributions', db.JSON, ...)` ব্যবহার করা হয়েছে)।

---

## ৩. একসাথে চালানোর জন্য (পূর্ণ স্ক্রিপ্ট)

নিচের ব্লক একবারে চালাতে পারবেন, যদি `teacher` টেবিল আগে থেকেই থাকে:

```sql
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
```

---

## ৪. চেকলিস্ট

- [ ] **blueprints/self_assessment/** পুরো ফোল্ডার সিপ্যানেলে আপলোড (models, routes, templates সহ)
- [ ] ডাটাবেজে `teacher` টেবিল আছে কিনা চেক
- [ ] উপরের SQL দিয়ে একের পর এক টেবিল তৈরি: `psac_committee` → `psac_committee_member` → `survey_link` → `survey_response` → `alumni_survey_response`
- [ ] অ্যাপ রিস্টার্ট করে `/self-assessment` ও সার্ভে লিংক টেস্ট

এই অনুযায়ী করলে শুধু Self Assessment এর ফাইল সিপ্যানেলে তুলে, বাকি ডাটাবেজ টেবিল ম্যানুয়ালি দিয়েই মডিউল চালু রাখতে পারবেন।
