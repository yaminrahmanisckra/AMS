# Curriculator cPanel এ তোলার গাইড

Curriculator মডিউল সিপ্যানেলে ডিপ্লয় করতে কোন ফাইলগুলো তুলতে হবে এবং ডাটাবেজে কী কী যোগ করতে হবে তার সংক্ষিপ্ত তালিকা।

---

## ১. যে ফাইলগুলো সিপ্যানেলে তুলতে হবে

### অ্যাপের মূল ফাইল (Curriculator চালু থাকার জন্য দরকার)

- `app.py` — Curriculator ব্লুপ্রিন্ট রেজিস্টার করা আছে
- `extensions.py`
- `user_models.py`
- `error_handler.py`
- `role_utils.py` (যদি থাকে)
- `passenger_wsgi.py` — cPanel Python অ্যাপের এন্ট্রি পয়েন্ট
- `requirements.txt` — Curriculator-এর জন্য বিশেষভাবে: `python-docx`, `weasyprint`, `PyMySQL` ইত্যাদি আছে কিনা দেখুন

### Curriculator ব্লুপ্রিন্ট — পুরো ফোল্ডার

```
blueprints/curriculator/
├── __init__.py
├── models.py
├── routes.py
└── templates/
    └── curriculator/
        ├── document_create.html
        ├── document_detail.html
        ├── document_import.html
        ├── export.html
        ├── index.html
        ├── part_a_section_edit.html
        ├── part_view.html
        └── permissions.html
```

**সবগুলোই তুলতে হবে** — একটা বাদ দিলে পেজ বা ফিচার ভাঙতে পারে।

### শেয়ার্ড টেমপ্লেট (যদি Curriculator ব্যবহার করে)

- `templates/base.html` — সাধারণ লেআউট
- ড্যাশবোয়ার্ড/নেভে Curriculator লিংক থাকলে সংশ্লিষ্ট টেমপ্লেট (যেমন `templates/dashboard.html`)

### মাইগ্রেশন ফাইল (ডাটাবেজ টেবিল আপডেটের জন্য)

```
migrations/
├── alembic.ini
├── env.py
└── versions/
    ├── b1f220be6847_add_curriculator_syllabus_tables.py
    ├── 4a84032bf12b_add_curriculator_editor_table.py
    ├── 446138e34525_add_year_term_type_status_prereq_to_.py
    ├── 4d5f3fe554cb_add_part_a_b_d_sections_and_section_.py
    └── (অন্যান্য যে মাইগ্রেশনগুলো আপনার চেইনে আছে)
```

**নোট:** `down_revision` চেইন মেনে সব প্রয়োজনীয় মাইগ্রেশন ফাইল থাকতে হবে; নাহলে `flask db upgrade` ভুল দেবে।

---

## ২. ডাটাবেজে যা যা থাকতে হবে

Curriculator চালানোর জন্য নিচের টেবিলগুলো **অবশ্যই** ডাটাবেজে থাকতে হবে। হয় মাইগ্রেশন চালিয়ে নেবেন, নয়তো নিচের টেবিলগুলো নিজে তৈরি করবেন।

### Curriculator-এর নিজস্ব টেবিল

| টেবিলের নাম | বর্ণনা |
|-------------|--------|
| `syllabus_document` | সিলেবাস ডকুমেন্ট (নাম, ব্যাচ ইত্যাদি) |
| `syllabus_part` | Part A/B/C/D (প্রতি ডকুমেন্টে চারটি পার্ট) |
| `syllabus_course_entry` | Part C-এর কোর্স এন্ট্রি (কোর্স কোড, টাইটেল, কনটেন্ট, CLO ইত্যাদি) |
| `syllabus_author_assignment` | কোন কোর্স এন্ট্রির অথর কে |
| `curriculator_editor` | কাদের সিলেবাস এডিট করার অনুমতি (Head দেওয়া ইউজার) |
| `syllabus_part_a_section` | Part A সেকশন ডেটা (PEO, PLO, ম্যাপিং ইত্যাদি) |
| `syllabus_part_b_config` | Part B কনফিগ (ডিউরেশন, টার্ম, এরিয়া-ওয়াইজ ইত্যাদি) |
| `syllabus_part_d_section` | Part D সেকশন (grading_scale, theory_evaluation, sessional_evaluation, approval_records) |
| `syllabus_section_assignment` | Part A সেকশনের মালিক/অ্যাসাইনমেন্ট (কোন ইউজার কোন সেকশন এডিট করবে) |

### অন্যান্য মডিউলের টেবিল (Curriculator যেগুলোর ওপর নির্ভর করে)

- `users` — লগইন ও অ্যাসাইনমেন্ট
- `course` — Part C কোর্স এন্ট্রি `course_id` দিয়ে লিংক করতে পারে
- `teacher` — অথর অ্যাসাইনমেন্ট ও Part A সেকশন

এই টেবিলগুলো সাধারণত অ্যাপের বাকি অংশ (Course Management, Class Management ইত্যাদি) ডিপ্লয় করার সময়ই তৈরি হয়ে থাকে।

---

## ৩. ডাটাবেজ সেটআপ করার দুটি উপায়

### উপায় ক: Flask-Migrate (Alembic) দিয়ে

সিপ্যানেল টার্মিনাল/SSH এ:

```bash
cd /path/to/your/app
source venv/bin/activate   # বা আপনার venv এক্টিভেট কমান্ড
flask db upgrade
```

এটা `migrations/versions/` এর চেইন অনুযায়ী সব টেবিল/কলাম তৈরি বা আপডেট করবে। Curriculator-সংবলিত মাইগ্রেশনগুলো যেন উপরে দেওয়া তালিকা অনুযায়ী সব আপলোড করা থাকে।

### উপায় খ: ম্যানুয়াল SQL (শুধু Curriculator টেবিল)

যদি মাইগ্রেশন চালানো সম্ভব না হয়, তাহলে নিচের টেবিলগুলো MySQL/phpMyAdmin এ চালিয়ে নিতে পারেন। **ক্রম মানতে হবে** (যে টেবিলের উপর FK আছে সে টেবিল আগে থাকতে হবে)।

1. `syllabus_document`
2. `syllabus_part` (FK: `document_id` → `syllabus_document.id`)
3. `syllabus_course_entry` (FK: `part_id` → `syllabus_part.id`, ঐচ্ছিক `course_id` → `course.id`)
4. `curriculator_editor` (FK: `user_id` → `users.id`)
5. `syllabus_author_assignment` (FK: `course_entry_id`, `teacher_id`, `assigned_by_id`)
6. `syllabus_part_a_section` (FK: `part_id` → `syllabus_part.id`)
7. `syllabus_part_b_config` (FK: `part_id` → `syllabus_part.id`)
8. `syllabus_part_d_section` (FK: `part_id` → `syllabus_part.id`)
9. `syllabus_section_assignment` (FK: `part_id`, `user_id`, `assigned_by_id`)

সঠিক কলাম ও টাইপের জন্য `blueprints/curriculator/models.py` এবং `migrations/versions/` এর সংশ্লিষ্ট মাইগ্রেশন ফাইল দেখুন; সেখান থেকে CREATE TABLE স্টেটমেন্ট বের করে phpMyAdmin এ রান করাতে পারেন।

---

## ৪. চেকলিস্ট

- [ ] `blueprints/curriculator/` পুরো ফোল্ডার (প্রতি টেমপ্লেট সহ) আপলোড হয়েছে
- [ ] `app.py` ও `passenger_wsgi.py` আপলোড হয়েছে
- [ ] `migrations/` এবং Curriculator-সংবলিত মাইগ্রেশন ফাইলগুলো আপলোড হয়েছে
- [ ] ডাটাবেজে উপরের সব টেবিল আছে (হয় `flask db upgrade` অথবা ম্যানুয়াল SQL)
- [ ] `users`, `course`, `teacher` টেবিল আছে (Curriculator এগুলো ব্যবহার করে)
- [ ] `.env` এ সঠিক `DATABASE_URL` (MySQL) দেওয়া আছে
- [ ] ভেন্বে `pip install -r requirements.txt` চালানো হয়েছে (যাতে `python-docx`, weasyprint ইত্যাদি থাকে)
- [ ] অ্যাপ রিস্টার্ট করার পর `/curriculator` পেজ খুলে লগইন করে চেক করা হয়েছে

---

## ৫. সংক্ষিপ্ত উত্তর

**কোন ফাইল তুলতে হবে:**  
- অ্যাপ রুট: `app.py`, `extensions.py`, `user_models.py`, `passenger_wsgi.py`, `requirements.txt` ইত্যাদি  
- **পুরো** `blueprints/curriculator/` (মডেল, রাউট, সব টেমপ্লেট)  
- `migrations/` এবং Curriculator-সম্পর্কিত মাইগ্রেশন ফাইল  
- প্রযোজ্য শেয়ার্ড টেমপ্লেট (যেমন `base.html`, `dashboard.html`)  

**ডাটাবেজে কী যোগ করতে হবে:**  
- উপরের ৯টি Curriculator টেবিল (`syllabus_document`, `syllabus_part`, `syllabus_course_entry`, `syllabus_author_assignment`, `curriculator_editor`, `syllabus_part_a_section`, `syllabus_part_b_config`, `syllabus_part_d_section`, `syllabus_section_assignment`)  
- এবং নিশ্চিত করতে হবে `users`, `course`, `teacher` টেবিল আগে থেকেই আছে।

এই অনুযায়ী ফাইল আপলোড ও ডাটাবেজ সেটআপ করলে Curriculator সিপ্যানেলে সচরাচর ঠিকভাবে চলে।
