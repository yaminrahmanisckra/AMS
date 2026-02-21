# Self Assessment মডিউল – cPanel ডিপ্লয়মেন্ট গাইড

সবগুলো সার্ভে মডিউল (Alumni, Employer, Student, Faculty, Non Academic Staff) cPanel-এ তুলতে নিচের ধাপগুলো অনুসরণ করুন।

---

## ০. কি কি ফাইল তুলতে হবে

### যা যা **আপলোড করতে হবে** (cPanel / সার্ভারে)

| ফোল্ডার/ফাইল | বর্ণনা |
|---------------|--------|
| **app.py** | মূল অ্যাপ এন্ট্রি |
| **passenger_wsgi.py** | cPanel Passenger ব্যবহার করলে |
| **requirements.txt** | পাইথন প্যাকেজ তালিকা |
| **user_models.py, models.py, extensions.py, role_utils.py, error_handler.py, email_config.py** | অ্যাপের মূল মডিউল |
| **blueprints/** | সব ব্লুপ্রিন্ট (auth, class_management, **self_assessment**, result_management, routine_management, course_management, academic_calendar, student_management, curriculator, remuneration_management) – প্রতিটির ভেতর `__init__.py`, `models.py`, `routes.py` এবং **templates** সাবফোল্ডার |
| **blueprints/self_assessment/** | Self Assessment এর জন্য অপরিহার্য: `models.py`, `routes.py`, **templates/self_assessment/** এর ভেতর সব `.html` (alumni/employer/student/faculty/non_academic survey ও form_pdf, response_pdf, response_view ইত্যাদি) |
| **templates/** | রুট টেমপ্লেট (base.html, login.html, dashboard.html ইত্যাদি) |
| **migrations/** | **env.py** এবং **versions/** এর ভেতর সব `.py` – `flask db upgrade` এর জন্য অপরিহার্য |
| **static/** | static/css, static/js, static/Images; পিডিএফে বাংলা চাইলে **static/Fonts/kalpurush.ttf** |
| **utils/** | অ্যাপে ব্যবহার হলে (websocket_events, semester_utils ইত্যাদি) |

**সংক্ষেপে:** প্রজেক্ট রুট থেকে **app.py, blueprints/, templates/, migrations/, static/, requirements.txt** এবং অ্যাপ চালানোর জন্য লাগা অন্য সব `.py` ফাইল আপলোড করুন। Self Assessment এর জন্য **blueprints/self_assessment/** পুরো ফোল্ডার এবং **migrations/** পুরো ফোল্ডার তুলতে হবে।

### যা **আপলোড করবেন না**

| বাদ দেবেন | কারণ |
|-----------|--------|
| **.env** | সিক্রেট ও ডাটাবেজ পাসওয়ার্ড – সিপ্যানেলে নতুন করে env সেট করবেন |
| **.git/** | গিট হিস্টরি (ক্লোন করলে ইচ্ছে করলে রাখতে পারেন) |
| **.venv/, venv/, env/** | লোকাল venv – সিপ্যানেলে নতুন venv বানিয়ে `pip install -r requirements.txt` চালাবেন |
| **__pycache__/** | পাইথন ক্যাশ – অটো জেনারেট হবে |
| **.cursor/, .idea/** | এডিটর সেটিং – ডিপ্লয়ের জন্য দরকার নেই |

**নোট:** `.env` এর মান সিপ্যানেলে Environment Variables বা নতুন `.env` এ ডাটাবেজ URL, FLASK_APP ইত্যাদি সেট করবেন; লোকাল `.env` কপি করে আপলোড করবেন না।

---

## ১. ডাটাবেজে যা যা যুক্ত হবে

Self Assessment এর জন্য নিচের টেবিলগুলো **migration** দিয়ে তৈরি হয়। নতুন কোনো টেবিল আলাদাভাবে ম্যানুয়াল যোগ করার দরকার নেই।

| টেবিল | বর্ণনা |
|-------|--------|
| `psac_committee` | PSAC কমিটির হেড (head_teacher_id), created_at, updated_at |
| `psac_committee_member` | কমিটি মেম্বার (committee_id, teacher_id, is_adhoc) |
| `survey_link` | পাবলিক সার্ভে লিংক (survey_type, access_code, title, committee_id) |
| `survey_response` | Employer/Student/Faculty/Non Academic রেসপন্স (survey_type, survey_link_id, payload JSON, ip_address) |
| `alumni_survey_response` | Alumni রেসপন্স (সব Part A–D ফিল্ড + survey_link_id) |

**Migration চেইন (যেই অর্ডারে চলে):**
```
add_course_content_classes
  → add_psac_committee        (psac_committee, psac_committee_member)
  → bb92084bacee              (alumni_survey_response)
  → add_survey_link           (survey_link, survey_response + alumni এ survey_link_id)
  → add_alumni_part_d         (alumni_survey_response এ Part D কলাম)
```

**করণীয়:** সিপ্যানেলে ডিপ্লয় করার পর একবার migration চালাতে হবে (নিচে ধাপ ৪)।

---

## ২. নতুন কোনো ডিপেন্ডেন্সি লাগবে কিনা

**না।** Self Assessment এর জন্য লাগা প্যাকেজগুলো ইতিমধ্যে `requirements.txt` এ আছে:

| প্যাকেজ | ব্যবহার |
|---------|---------|
| `weasyprint==52.5` | ব্ল্যাঙ্ক ফরম ও রেসপন্স পিডিএফ জেনারেট (cPanel এর পুরনো Pango 1.42.x এর সাথে কম্প্যাটিবল) |
| `PyPDF2==1.26.0` | “Download All responses” – একাধিক পিডিএফ মার্জ করে একটা ফাইলে দেওয়া |

অন্য যে ডিপেন্ডেন্সি অ্যাপ ইতিমধ্যে ব্যবহার করে (Flask, Flask-Login, SQLAlchemy, Jinja2, ইত্যাদি) সেগুলোই যথেষ্ট। তাই **নতুন প্যাকেজ ইনস্টল বা requirements.txt এ নতুন লাইন যোগ করার দরকার নেই।**

---

## ৩. cPanel এ যা করতে হবে (সংক্ষেপে)

1. **অ্যাপ আপলোড**  
   প্রজেক্টের ফাইলগুলো (অথবা Git দিয়ে ক্লোন) cPanel এর অ্যাপ ফোল্ডারে আপলোড করুন।

2. **Python অ্যাপ সেটআপ**  
   cPanel → **Setup Python App** / **Application Manager** থেকে:
   - Python ভার্সন সিলেক্ট করুন (যে ভার্সন দিয়ে লোকালে টেস্ট করেছেন, যেমন 3.10/3.11)।
   - Application root ও Entry point সঠিক রাখুন (যেমন `app:app` বা `wsgi:application`)।
   - Virtual environment ক্রিয়েট করুন।

3. **ডিপেন্ডেন্সি ইন্সটল**  
   একবার SSH বা “Run setup” দিয়ে:
   ```bash
   source /path/to/venv/bin/activate
   pip install -r requirements.txt
   ```
   ইতিমধ্যে `weasyprint` ও `PyPDF2` requirements এ থাকায় আলাদা ইনস্টল করার দরকার নেই।

4. **এনভায়রনমেন্ট ভেরিয়েবল**  
   `.env` বা cPanel এর env section এ:
   - `FLASK_APP=app.py` (অথবা আপনার মূল অ্যাপ ফাইল)
   - `DATABASE_URL` বা `SQLALCHEMY_DATABASE_URI` – cPanel MySQL/PostgreSQL এর জন্য সঠিক connection string।
   - অ্যাপের অন্য যে env ভেরিয়েবল লাগে (সিক্রেট কি, মেইল, ইত্যাদি) সেগুলোও দিন।

5. **ডাটাবেজ মাইগ্রেশন**  
   প্রথম ডিপ্লয় বা নতুন সিপ্যানেল সেটআপের পর একবার চালান:
   ```bash
   source /path/to/venv/bin/activate
   export FLASK_APP=app.py   # অথবা আপনার অ্যাপ
   flask db upgrade
   ```
   এতে উপরের সব Self Assessment টেবিল (psac_committee, survey_link, survey_response, alumni_survey_response ইত্যাদি) ক্রমে ক্রিয়েট/আপডেট হবে।

6. **WeasyPrint (পিডিএফ)**  
   প্রজেক্টে ইতিমধ্যে `weasyprint==52.5` cPanel এর পুরনো Pango (১.৪২.x) এর সাথে কাজ করার জন্য রাখা হয়েছে। যদি সিপ্যানেলে WeasyPrint ইন্সটল হওয়ার সময় লাইব্রেরি এরর আসে (যেমন Pango/Cairo না মিলা), তাহলে হোস্টিং সাপোর্ট থেকে সেই সিস্টেম লাইব্রেরি ভার্সন জেনে নিন; প্রয়োজন হলে `LD_LIBRARY_PATH` সেট করে দিতে হতে পারে।

7. **অপশনাল: কালপুরুষ ফন্ট**  
   বাংলা টেক্সট পিডিএফে চাইলে অ্যাপের `static/Fonts/` (বা `static/fonts/`) ফোল্ডারে `kalpurush.ttf` রাখুন। না থাকলেও ইংরেজি পিডিএফ ঠিকভাবে জেনারেট হবে।

8. **রিস্টার্ট**  
   env বা কোড পরিবর্তনের পর Python অ্যাপ একবার রিস্টার্ট করুন (cPanel এ সাধারণত “Restart” বাটন থাকে)।

---

## ৪. চেকলিস্ট

- [ ] প্রজেক্ট ফাইল / Git ক্লোন cPanel এ আপলোড
- [ ] Python অ্যাপ সেটআপ (ভার্সন, venv, entry point)
- [ ] `pip install -r requirements.txt` চালানো
- [ ] `.env` / env ভেরিয়েবল সেট (ডাটাবেজ URL, FLASK_APP ইত্যাদি)
- [ ] `flask db upgrade` চালানো (Self Assessment সহ সব টেবিল আপডেট)
- [ ] WeasyPrint এরর থাকলে লাইব্রেরি/পাথ চেক
- [ ] (অপশনাল) `static/Fonts/kalpurush.ttf` আপলোড
- [ ] অ্যাপ রিস্টার্ট করে `/self-assessment` ও পাবলিক সার্ভে লিংক টেস্ট

---

## ৫. সংক্ষেপ

| প্রশ্ন | উত্তর |
|--------|--------|
| ডাটাবেজে কী কী যুক্ত হবে? | `psac_committee`, `psac_committee_member`, `survey_link`, `survey_response`, `alumni_survey_response` – সব **migration** দিয়ে; আলাদা ম্যানুয়াল টেবিল না। |
| নতুন ডিপেন্ডেন্সি? | না। `weasyprint` ও `PyPDF2` ইতিমধ্যে requirements এ আছে। |
| এক্সট্রা স্টেপ? | ডিপ্লয় পর **একবার** `flask db upgrade` চালানো এবং (প্রয়োজন হলে) WeasyPrint লাইব্রেরি/পাথ ঠিক করা। |

এই গাইড অনুযায়ী করলে Self Assessment এর সব সার্ভে মডিউল cPanel এ চালু থাকার কথা।
