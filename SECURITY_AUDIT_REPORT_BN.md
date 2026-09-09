# Academic Management System (AMS) — সিকিউরিটি অডিট রিপোর্ট ও প্রোডাকশন-রেডিনেস প্ল্যান

- **অডিটের তারিখ:** ৪ সেপ্টেম্বর ২০২৬
- **কমিট:** `b790292` (Harden production sessions and file serving…)
- **পদ্ধতি:** সম্পূর্ণ সোর্স কোডের স্ট্যাটিক রিভিউ (`app.py` ~১৮.৭k লাইন, ১৩টি blueprint, `utils/`, টেমপ্লেট, ডিপ্লয়মেন্ট ফাইল, CI ওয়ার্কফ্লো, git ট্র্যাকিং), OSV ডাটাবেসে ডিপেন্ডেন্সি CVE স্ক্যান, এবং Critical ইস্যুর জন্য অফলাইন Proof-of-Concept। কোনো লাইভ সার্ভারে আক্রমণ চালানো হয়নি; কোনো কোড পরিবর্তন করা হয়নি।
- **স্কোপ বহির্ভূত:** cPanel সার্ভারের বাস্তব কনফিগ (যা রিপোতে নেই), MySQL সার্ভার হার্ডেনিং, নেটওয়ার্ক/ফায়ারওয়াল।

> **সতর্কতা:** এই রিপোর্টে যেসব দুর্বলতা আছে তা অ্যাপটি বর্তমানে যে অবস্থায় আছে তাতে **প্রোডাকশনে চালানো নিরাপদ নয়**। অন্তত Section 3-এর সব **Critical** ও **High** ইস্যু ঠিক না করে পাবলিক ইন্টারনেটে এটি চালু রাখা উচিত নয়।

---

## ১. সারসংক্ষেপ (Executive Summary)

| Severity | সংখ্যা | সারকথা |
|---|---|---|
| **Critical** | ৬ | পাসওয়ার্ড-রিসেট কোড অফলাইনে ব্রুট-ফোর্স করে **যে-কোনো অ্যাকাউন্ট (অ্যাডমিনসহ) দখল**; লগইন ছাড়াই কোর্স-অ্যাসাইনমেন্ট তৈরি/সম্পাদনা; যে-কোনো শিক্ষক/TA অন্যের ক্লাসের ছাত্র মুছতে/বদলাতে পারে; `public_html`-এর ভেতরে অ্যাপ অথচ `.htaccess`-এ কোনো deny রুল নেই; CI ডিপ্লয়ে TLS ভেরিফিকেশন বন্ধ; Critical CVE-যুক্ত লাইব্রেরি (Pillow RCE, PyMySQL SQLi)। |
| **High** | ১৬ (+৫টি High-CVE প্যাকেজ) | CSRF সুরক্ষা ডিফল্টে বন্ধ; নোটিসবোর্ডে Stored XSS; অ্যাডমিশন পোর্টালে PIN ব্রুট-ফোর্স; `has_role()`-এ active_role নিষ্ক্রিয়; Result Management-এ cross-session IDOR; ব্যবহারকারী/প্রার্থীর ছবি-স্বাক্ষর-ব্যাংক স্লিপ পাবলিক `static/`-এ; hard-coded `admin/admin123`; CI-তে পাসওয়ার্ড-SSH ও ভাঙা ডিপ্লয়; git-এ ৬৬ MB zip/venv/ছবি; SMTP TLS verify বন্ধ; ইত্যাদি। |
| **Medium** | ২৫ (+৩টি Medium-CVE প্যাকেজ) | Exception বার্তা ক্লায়েন্টে ফেরত (১১০+ জায়গায়), সিকিউরিটি হেডার নেই, referrer open-redirect, AI base-URL SSRF, ইমেইল হেডার ইনজেকশন সম্ভাবনা, request-time `db.create_all()`, ডিবাগ লগে ছাত্রের নম্বর, Socket.IO গ্লোবাল broadcast, TA-র পূর্ণ শিক্ষক-প্রিভিলেজ, ইত্যাদি। |
| **Low / Info** | ১৫ | পাসওয়ার্ড নীতি দুর্বল, user enumeration, logout GET, LIKE wildcard, ডকুমেন্টেশনে হোস্ট-তথ্য, ইত্যাদি। |

**ইতিবাচক দিক (যা ইতিমধ্যে ঠিক আছে):** PBKDF2-SHA512 পাসওয়ার্ড হ্যাশ; প্রোডাকশনে দুর্বল `SECRET_KEY` ও SQLite fallback প্রত্যাখ্যান; HttpOnly/SameSite cookie; hop-সীমিত ProxyFix; Socket.IO connect/room অথরাইজেশন; `utils/safe_files.py` path-confinement; `yaml.safe_load`; parameterized SQL (কোনো classic SQLi পাওয়া যায়নি); course-outline HTML sanitizer; redacted 500-error handler; DB-backed login throttle; append-only audit log; impersonation guard; রেজিস্ট্রেশন বন্ধ; ফর্ম থেকে `admin` role গ্রহণ না করা।

---

## ২. Severity সংজ্ঞা

- **Critical** — লগইন ছাড়া বা সাধারণ ব্যবহারকারী হিসেবে সম্পূর্ণ অ্যাকাউন্ট/ডেটা দখল বা ব্যাপক ডেটা-লস সম্ভব।
- **High** — অথেনটিকেটেড ব্যবহারকারীর প্রিভিলেজ এস্কালেশন, অন্যের ডেটা পড়া/বদলানো, বা সেশন হাইজ্যাক।
- **Medium** — সীমিত প্রভাব, অথবা অন্য দুর্বলতার সাথে মিলে বড় আক্রমণে সহায়ক।
- **Low / Info** — best-practice লঙ্ঘন, তথ্য ফাঁস, hardening।

---

## ৩. বিস্তারিত ফাইন্ডিং তালিকা

### ৩.১ অথেনটিকেশন ও সেশন (AUTH)

| ID | Severity | সমস্যা | অবস্থান |
|---|---|---|---|
| **AUTH-01** | **Critical** | **পাসওয়ার্ড-রিসেট কোড অফলাইনে ব্রুট-ফোর্স → যে-কোনো অ্যাকাউন্ট টেকওভার।** `forgot_password` ৬-ডিজিট কোডের **unsalted SHA-256** (`ch`) একটি `URLSafeTimedSerializer` টোকেনে (`challenge`) রাখে। itsdangerous টোকেন কেবল *signed*, *encrypted নয়* — payload base64/zlib দিয়ে যে-কেউ পড়তে পারে। এই `challenge` অনুরোধকারীর (অর্থাৎ আক্রমণকারীর) session cookie-তে **এবং** `verify_reset_code.html`-এর hidden field-এ ফেরত দেওয়া হয়। আক্রমণকারী: (১) ভিকটিমের ইমেইল দিয়ে forgot-password সাবমিট, (২) challenge ডিকোড করে `ch` বের করে, (৩) ১০ লক্ষ SHA-256 হ্যাশ অফলাইনে মিলিয়ে কোড বের করে (**PoC: ০.০৪ সেকেন্ড**), (৪) `/account/verify-code`-এ challenge+code+নতুন পাসওয়ার্ড পাঠায়। ইমেইল ইনবক্সে ঢোকার প্রয়োজনই নেই। অ্যাডমিন অ্যাকাউন্টও একই ভাবে দখলযোগ্য। এছাড়া verify endpoint-এ **কোনো rate-limit নেই**, অর্থাৎ অনলাইন ব্রুট-ফোর্সও সম্ভব। | `blueprints/auth/routes.py:437` (`_hash_reset_code`), `455-464` (challenge-এ `ch`), `555` (session-এ), `582-651` (`verify_reset_code`); `blueprints/auth/templates/auth/verify_reset_code.html:26` |
| **AUTH-02** | **High** | **CSRF সুরক্ষা ডিফল্টে বন্ধ।** `WTF_CSRF_CHECK_DEFAULT=False`; `CSRF_ENABLED=true` না দিলে কোনো POST endpoint-এ CSRF যাচাই হয় না। `env.example`-ও `false`। SameSite=Lax আংশিক রক্ষা দেয়, কিন্তু (ক) GET-ভিত্তিক state change (যেমন `/logout`), (খ) Chrome-এর "Lax+POST" ২-মিনিট ব্যতিক্রম, (গ) পুরনো ব্রাউজার — এসবে কাজ করে না। `WTF_CSRF_TIME_LIMIT=None`-ও টোকেনকে চিরস্থায়ী করে। অ্যাডমিশন পোর্টালের সব POST `@csrf.exempt`। | `app.py:227-231, 349-351`; `env.example:14`; `blueprints/admission_exam/routes.py:3183, 3360, 3423, 3494, 3537, 3567` |
| **AUTH-03** | **High** | **অ্যাডমিশন প্রার্থী লগইনে ব্রুট-ফোর্স সুরক্ষা নেই।** Application ID ক্রমিক (`PREFIX-0001`, `0002`…) ও অনুমানযোগ্য; PIN ৬ ডিজিট; `/apply/<token>/login` পাবলিক, CSRF-exempt, কোনো throttle/lockout নেই। সফল হলে প্রার্থীর ছবি, স্বাক্ষর, সনদপত্র, ফোন, ব্যাংক স্লিপ দেখা ও পেমেন্ট-তথ্য/ডকুমেন্ট বদলানো যায়। প্রতি চেষ্টায় PBKDF2 হ্যাশিং হওয়ায় CPU-DoS-ও সম্ভব। | `blueprints/admission_exam/routes.py:234-245` (PIN/ID জেনারেশন), `3359-3378` (`candidate_login`) |
| **AUTH-04** | **High** | **forgot-password / reset / register endpoint-এ কোনো rate-limit নেই** → ভিকটিমকে ইমেইল-বোমা, SMTP কোটা শেষ, AUTH-01-এর অনলাইন রূপ। `flask-limiter` বা সমতুল্য ইনস্টল নেই। | `blueprints/auth/routes.py:441, 582, 654, 660` |
| **AUTH-05** | **Medium** | **Login throttle বাইপাসযোগ্য ও fail-open।** কী = `username+IP` → IP বদলালে (proxy/botnet) প্রতি IP-তে নতুন ৮ চেষ্টা; একই IP থেকে বহু username-এ credential stuffing-এ কোনো সীমা নেই; `login_throttle` টেবিল না থাকলে বা DB error হলে নিঃশব্দে সুরক্ষা বন্ধ। | `utils/login_throttle.py:21-22, 39-54` |
| **AUTH-06** | **Medium** | **Legacy reset link-এ পাসওয়ার্ড দৈর্ঘ্য যাচাই নেই**; পুরনো টোকেন ফরম্যাটে (`pf` ছাড়া) fingerprint check বাদ যায় (backward-compat)। | `blueprints/auth/routes.py:666-704` |
| **AUTH-07** | **Medium** | **দুর্বল পাসওয়ার্ড নীতি।** ন্যূনতম ৬ অক্ষর (কোথাও তাও নেই — `profile` রুটে নতুন পাসওয়ার্ডে কোনো দৈর্ঘ্য চেক নেই); জটিলতা/common-password/breach চেক নেই। | `blueprints/auth/routes.py:626`; `app.py:18216, 18317, 18497` |
| **AUTH-08** | **Low** | **User enumeration:** ইমেইল থাকলে "verification code sent" + redirect, না থাকলে uniform message; SMTP ব্যর্থ হলেও ভিন্ন বার্তা। | `blueprints/auth/routes.py:556-578` |
| **AUTH-09** | **Low** | `/logout` GET → CSRF দিয়ে জবরদস্তি logout; `login.html`-এ dev-only ngrok লজিক প্রোডাকশনে রয়ে গেছে। | `blueprints/auth/routes.py:124-136, 297` |
| **AUTH-10** | **Medium** | **নিরীক্ষা (audit) ফাঁক:** login success/failure, lockout, `login_as` impersonation শুরু/শেষ, ইমেইল-ভিত্তিক password reset — কোনোটাই `audit_log`-এ লেখা হয় না (কেবল user.create/update/delete/password_reset ও marks save লেখা হয়)। | `blueprints/auth/routes.py` (সমগ্র); `utils/audit.py` |

### ৩.২ অথরাইজেশন / IDOR (AUTHZ)

| ID | Severity | সমস্যা | অবস্থান |
|---|---|---|---|
| **AUTHZ-01** | **Critical** | **লগইন ছাড়াই কোর্স-অ্যাসাইনমেন্ট তৈরি/সম্পাদনা।** `assign_course` (GET/POST) ও `edit_assignment` (GET/POST)-এ `@login_required` নেই এবং `routine_management` blueprint-এ কোনো `before_request` গার্ড নেই। GET-এ ফর্ম (CSRF টোকেনসহ) পাওয়া যায়, তারপর POST-এ যে-কোনো শিক্ষককে যে-কোনো কোর্সে বসানো/সরানো যায়। | `blueprints/routine_management/routes.py:1108-1184, 1187+` |
| **AUTHZ-02** | **High** | **লগইন ছাড়াই রুটিন/শিক্ষক তালিকা/PDF ডাউনলোড।** `/api/get_teachers`, `/api/routine/load`, `/download_teacher_wise_pdf`, `/download_course_wise_pdf` অ্যানোনিমাসভাবে খোলা। | `blueprints/routine_management/routes.py:1836, 3161, 3729, 3791` |
| **AUTHZ-03** | **Critical** | **Class Management-এ ownership check ছাড়া ছাত্র সম্পাদনা/মুছা।** `edit_student`/`delete_student` সরাসরি `ClassStudent.query.get_or_404(id)` — কোনো teacher-ownership বা window check নেই। শিক্ষক-প্রিভিলেজধারী যে-কেউ (student+Teaching Assistant সহ) অন্য যে-কোনো ক্লাসের ছাত্রের ID/নাম বদলাতে বা attendance-সহ মুছে দিতে পারে (`_replicate_student_to_peers` দিয়ে split-course peers-এও ছড়ায়)। | `blueprints/class_management/routes.py:4629-4641, 4643-4680` |
| **AUTHZ-04** | **High** | **অন্যের ক্লাস-সেশন পরিবর্তন:** `add_student`, `upload_students` (Excel), `archive_session`, `unarchive_session`, `edit_session`, `course-assessment` (evaluator invite), `students/<id>` ও `evaluation/<id>` তালিকা — সবই কেবল window-scoped, ownership check নেই। ১৩,২০০ লাইনের এই ফাইলে `user_owns_class_session` মাত্র ৬ বার ব্যবহৃত (attendance/assessment রুটে ঠিক আছে)। | `blueprints/class_management/routes.py:3541, 4524, 6889, 6899, 6909, 10072-10121, 4284-4303, 10064-10070` |
| **AUTHZ-05** | **High** | **Result Management: tabulator cross-session access।** `_can_access_session()` কেবল কিছু রুটে; `edit_student`, `delete_student`, `delete_subject` এবং সব PDF/ZIP download রুট কেবল window-scoped helper (`_get_rstudent_or_404` → `get_or_404_for_window`) ব্যবহার করে। এক সেশনের tabulator হিসেবে নিযুক্ত শিক্ষক অন্য সেশনের ছাত্র/subject মুছতে ও ফলাফল ডাউনলোড করতে পারে। | `blueprints/result_management/routes.py:1041-1074` (helper), `1604-1646`, `2400-2427`, `4642+` |
| **AUTHZ-06** | **High** | **`has_role()` stored ও active role-এর union নেয়** → লগইনের সময় বেছে নেওয়া `active_role` কোনো নিরাপত্তা-সীমা তৈরি করে না। `head,teacher` ব্যবহারকারী "teacher" হিসেবে লগইন করেও head-only `role_required` পাস করে; `student,teaching_assistant` ব্যবহারকারী "student" হিসেবে ঢুকেও TA-প্রিভিলেজ পায়। `is_admin`/`has_teacher_privileges` আবার active_role মানে — অসঙ্গতি। | `role_utils.py:221-231`, `256-277` |
| **AUTHZ-07** | **High** | **নাম-ভিত্তিক শিক্ষক পরিচয় (identity by `full_name`)।** `resolve_caller_teacher()` ও `_ensure_current_teacher()` `Teacher.name == user.full_name` দিয়ে fallback করে। প্রোফাইলে নাম-লক কেবল teacher/head/dean বা `teacher_id`-লিঙ্কড ব্যবহারকারীর জন্য; **TA/student/officer** নিজের নাম বদলে (কোনো User-এর নাম না মিললেই হয়) কোনো Teacher রো-এর (যেমন external teacher, যার User নেই) নাম নিলে সেই শিক্ষকের সেশনের মালিকানা পেয়ে যায়। | `utils/ownership.py:34-39`; `blueprints/class_management/routes.py:1712-1714`; `app.py:18365-18393` |
| **AUTHZ-08** | **Medium** | **Teaching Assistant = পূর্ণ শিক্ষক-প্রিভিলেজ।** `TEACHING_ROLES` এ TA থাকায় TA (যিনি একই সাথে student) Class Management-এর সব শিক্ষক-রুট, নোটিস কম্পোজ, ইত্যাদিতে ঢুকতে পারে; AUTHZ-03/04-এর সাথে মিলে ছাত্রও অন্য ক্লাসের ডেটা বদলাতে পারে। | `role_utils.py:24-26`; `blueprints/class_management/routes.py:1680-1710`; `blueprints/noticeboard/audience.py:13-17` |
| **AUTHZ-09** | **Medium** | **Socket.IO broadcast সবার কাছে:** `session_created`, `result_updated`, `routine_updated`, `course_updated`, `student_updated` default namespace-এ **সব লগইন করা ক্লায়েন্টে** পাঠানো হয় (room-scoped নয়) → ছাত্রও ফলাফল/সেশন-মেটাডেটা ইভেন্ট পায়। | `utils/websocket_events.py:64-74, 91-142` |
| **AUTHZ-10** | **Medium** | **Cross-window data access:** যেসব রুট বেয়ার `Model.query.get_or_404` ব্যবহার করে (AUTHZ-03 সহ) সেগুলো operational-window isolation-ও ভাঙে। (`get_effective_window_id` নিজে request param বিশ্বাস করে না — ভালো।) | `blueprints/class_management/routes.py:4633, 4648`; `utils/window_utils.py` |
| **AUTHZ-11** | **Low** | Admin `edit_user`-এ ইমেইল ফরম্যাট যাচাই নেই; `Teacher` রেকর্ড নাম-ম্যাচে auto-link হয় (ভুল লিঙ্ক সম্ভব)। | `app.py:18090-18111` |

### ৩.৩ XSS, ইনজেকশন, redirect, SSRF (INJ)

| ID | Severity | সমস্যা | অবস্থান |
|---|---|---|---|
| **INJ-01** | **High** | **Noticeboard-এ Stored XSS।** `body_html` TinyMCE থেকে যেমন আসে তেমনই DB-তে সেভ (কোনো sanitizer নেই) এবং টেমপ্লেটে Jinja-র `safe` ফিল্টার দিয়ে (autoescape বন্ধ করে) সবার কাছে রেন্ডার। কম্পোজার = `has_teacher_privileges` (TA সহ)। `<script>`/`onerror=` দিয়ে যে-কোনো দর্শকের (অ্যাডমিন সহ) ব্রাউজারে JS চালিয়ে user তৈরি/পাসওয়ার্ড রিসেট/মার্কস বদল সম্ভব (cookie HttpOnly হলেও same-origin request চলে)। PDF রেন্ডারেও (WeasyPrint) একই HTML যায়। | `blueprints/noticeboard/routes.py:363-377, 460-473`; `templates/noticeboard/detail.html:45`; `notice_pdf.html:92` |
| **INJ-02** | **Medium** | **DOM XSS:** exam-committee chief dashboard-এ `member.name`, `designation`, `institute` escape ছাড়া `innerHTML`-এ। ডেটা অ্যাডমিন/হেড-নিয়ন্ত্রিত হলেও profile/teacher নামে HTML থাকলে ট্রিগার হয়। অন্য টেমপ্লেটে আরও `innerHTML` ব্যবহার আছে (spot-check: অধিকাংশ `qbEscapeHtml`/`tojson` ব্যবহার করে)। | `templates/exam_committee_chief/dashboard.html:1048-1068` |
| **INJ-03** | **Medium** | **Open redirect via `Referer`:** `redirect(request.referrer or …)` ৬ জায়গায়; CSRF বন্ধ থাকায় cross-site POST-এর পর আক্রমণকারীর সাইটে redirect (phishing)। (`_safe_next_url` আছে কিন্তু এখানে ব্যবহৃত হয়নি।) | `blueprints/admission_exam/routes.py:3945, 4207, 4243, 4492` ও আরও ২ |
| **INJ-04** | **Medium** | **SSRF via AI provider base URL:** অ্যাডমিন-কনফিগারযোগ্য `api_base_url` সরাসরি `urllib.request.urlopen`-এ; কোনো host/scheme allowlist বা private-IP block নেই → আপোসকৃত অ্যাডমিন সেশন (INJ-01 দিয়ে সম্ভব) দিয়ে অভ্যন্তরীণ সার্ভিস/metadata endpoint প্রোব। | `utils/ai/client.py:113-118, 191, 250, 290`; `app.py:3878-4041` |
| **INJ-05** | **Medium** | **ইমেইল হেডার ইনজেকশন সম্ভাবনা:** `msg['To'] = recipient` raw; ব্যবহারকারী/অ্যাডমিন ইমেইলে `\r\n` থাকলে অতিরিক্ত হেডার। ইমেইল ফরম্যাট কোথাও কঠোরভাবে validate হয় না (`email-validator` ইনস্টল থাকলেও অব্যবহৃত)। | `utils/recovery_email.py:110`; `app.py:18091, 18199, 18350` |
| **INJ-06** | **Low** | `Content-Disposition` filename-এ `sanitize_filename` `\r\n` সরায় না (course code স্টাফ-নিয়ন্ত্রিত)। | `app.py:2657-2687` |
| **INJ-07** | **Low** | `ilike(f'%{search}%')` — `%`/`_` wildcard injection (SQLi নয়, কিন্তু full-table match/DoS)। | `blueprints/student_management/routes.py:145-153` ও অন্যান্য search |
| **INJ-08** | **Info** | **SQL injection পাওয়া যায়নি** — raw `text()` কুয়েরি সব parameterized/fixed-column; `subprocess` list-form ও `-dSAFER`; `yaml.safe_load`; কোনো `eval/pickle`। Ghostscript/pdftoppm দিয়ে untrusted PDF রাস্টারাইজ একটি ঝুঁকি-পৃষ্ঠ (কেবল অ্যাডমিন-আপলোড)। | — |

### ৩.৪ ফাইল আপলোড ও স্টোরেজ (FILE)

| ID | Severity | সমস্যা | অবস্থান |
|---|---|---|---|
| **FILE-01** | **High** | **ব্যবহারকারীর ছবি ও ডিজিটাল স্বাক্ষর পাবলিক।** `static/uploads/user_photos/user_<id>_<unix_ts>.<ext>` ও `static/uploads/user_signatures/…` Apache/Flask static দিয়ে **লগইন ছাড়া** সার্ভ হয়; নাম আংশিক অনুমানযোগ্য। স্বাক্ষরের ছবি admission/remuneration ডকুমেন্টে ব্যবহৃত হয় — জালিয়াতির উপকরণ। | `app.py:330-334, 18436-18442`; `utils/user_signature.py:79-87` |
| **FILE-02** | **High** | **অ্যাডমিশন প্রার্থীর ছবি/স্বাক্ষর/ব্যাংক-স্লিপ/সনদ পাবলিক `static/`-এ।** `static/uploads/admission_exam/cycle_<id>/<APPID>_photo_<unix_ts>.jpg` — APPID ক্রমিক, timestamp সেকেন্ড-রেজোলিউশন → দিনে ৮৬,৪০০ URL চেষ্টা করে প্রত্যেক প্রার্থীর ছবি/ব্যাংক স্লিপ (অ্যাকাউন্ট নম্বরসহ) নামানো সম্ভব। authenticated রুট (`/apply/<token>/photo`) থাকলেও static path বাইপাস করে। | `blueprints/admission_exam/routes.py:248-254, 296-306, 354-358` |
| **FILE-03** | **Medium** | **Q&A attachment-এ extension allowlist/magic check নেই** — `.html/.svg/.exe/.py` আপলোড সম্ভব; ডাউনলোডে `as_attachment=True` থাকায় ব্রাউজার-XSS কম, কিন্তু ম্যালওয়ার বিতরণ ও ডিস্ক DoS সম্ভব। | `blueprints/class_management/routes.py:2536-2559` |
| **FILE-04** | **Medium** | **প্রার্থীর সনদপত্র raw সেভ** (`file_storage.save`) — কেবল extension চেক, Pillow re-encode নেই (ছবি/স্বাক্ষরে আছে) → polyglot/ম্যালফর্মড ফাইল স্টোর। | `blueprints/admission_exam/routes.py:336-358` |
| **FILE-05** | **Medium** | **Landing attachment-এ `zip/rar`/office ফাইল অনুমোদিত ও পাবলিক ডাউনলোড** — অ্যাডমিন অ্যাকাউন্ট আপোস হলে ম্যালওয়ার হোস্টিং। | `blueprints/admission_exam/routes.py:77-80, 3832-3881, 3913-3930` |
| **FILE-06** | **Low** | ডকুমেন্ট delete-এ DB রো মুছলেও ডিস্কের ফাইল থাকে; profile photo-এ content-type/magic check নেই (extension only)। | `blueprints/admission_exam/routes.py:3566-3583`; `app.py:18414-18418` |
| **FILE-07** | **Info** | ভালো: `utils/safe_files.py` realpath-confinement; photo/signature Pillow re-encode; `secure_filename` + uuid নাম; `MAX_CONTENT_LENGTH=16MB`। | — |

### ৩.৫ সিক্রেট, কনফিগ ও ডিপ্লয়মেন্ট (CONF)

| ID | Severity | সমস্যা | অবস্থান |
|---|---|---|---|
| **CONF-01** | **Critical** | **অ্যাপ `public_html`-এর ভেতরে, `.htaccess`-এ কোনো deny রুল নেই।** `PassengerAppRoot "/home/kulawams/public_html/ams"` — Passenger বন্ধ/মিসকনফিগ হলে বা static-এর মতো path-এ Apache সরাসরি `.env`, `*.py` (সোর্স), `instance/*.db`, `logs/*.log`, `tmp/*.csv` (ছাত্রের নম্বর), `*.md`, `.git/` সার্ভ করবে। `scripts/security/htaccess_archive/.htaccess.kulawams.fixed`-এ FilesMatch-deny/`Options -Indexes` আছে কিন্তু লাইভ `.htaccess`-এ **প্রয়োগ হয়নি**। | `.htaccess` (root); `scripts/security/htaccess_archive/*`; `scripts/security/docroot_cleanup.md` |
| **CONF-02** | **Critical** | **CI ডিপ্লয়ে TLS ভেরিফিকেশন বন্ধ** (`verify=False`) — cPanel API-এ পাসওয়ার্ড ও সোর্স পাঠানোর সময় MITM → ক্রেডেনশিয়াল/সার্ভার দখল। | `.github/workflows/deploy-cpanel-api.yml:84,96,108,152,186`; `deploy-cpanel-shared.yml:86,98,110,174,188` |
| **CONF-03** | **High** | **CI: পাসওয়ার্ড-ভিত্তিক SSH, `/public_html/` রুটে ডিপ্লয়, `create_admin.py` প্রোডাকশনে কপি, তৃতীয়-পক্ষ Action tag-pinned (SHA নয়), এবং `requirements_cpanel.txt` ফাইল আসলে নেই** (ওয়ার্কফ্লো ভাঙা/ভুল ডিপেন্ডেন্সি)। | `.github/workflows/deploy-cpanel.yml` (সম্পূর্ণ) |
| **CONF-04** | **High** | **লোকাল `.env`-এ আসল OpenAI API key** (`sk-…`, ১৬৪ অক্ষর)। git-ignored ঠিকই, কিন্তু প্রজেক্ট ফোল্ডার কপি/জিপ/শেয়ার হলে ফাঁস; **রোটেট করা উচিত**। | `.env:2` |
| **CONF-05** | **High** | **Hard-coded `admin`/`admin123`** — `reset_database_complete.py` চালালে জানা পাসওয়ার্ডের অ্যাডমিন তৈরি হয়; স্ক্রিপ্ট git-tracked ও deployment zip-এ। `clear_database.py`/`reset_database.py` (ধ্বংসাত্মক) ও ট্র্যাকড। | `reset_database_complete.py:59, 66`; `clear_database.py`; `reset_database.py` |
| **CONF-06** | **High** | **Git-এ অনুচিত ফাইল:** `cpanel_deployment.zip` (৬৬ MB, ভেতরে পূর্ণ `.venv/` ৮৩০০+ ফাইল + user photos), `venv_test/` (২০ ফাইল), `venv_feedback/` (১২), `static/uploads/user_photos/*` (২ জন ব্যবহারকারীর ছবি), `.git 2` worktree pointer। রিপো পাবলিক হলে PII ফাঁস; ইতিহাস purge লাগবে। | `git ls-files` |
| **CONF-07** | **High** | **SMTP TLS ভেরিফিকেশন বন্ধ:** `MAIL_SSL_VERIFY=False` উদাহরণে এবং কোডে `CPANEL=1` হলে ডিফল্টে `CERT_NONE` → পাসওয়ার্ড-রিসেট কোডসহ মেইল MITM। `MAIL_USE_SENDMAIL` fallback-ও ডিফল্টে চালু। | `env.example:51`; `utils/recovery_email.py:60-79, 366` |
| **CONF-08** | **Medium** | **AI key encryption `SECRET_KEY`-এর উপর নির্ভর** (dedicated `AI_KEY_ENCRYPTION_SECRET` না দিলে) ও কোডে hard-coded fallback `'a_very_secret_default_key'`; `get_serializer()`-এও একই fallback স্ট্রিং। | `utils/ai/encryption.py:27-32, 40-41`; `blueprints/auth/routes.py:416` |
| **CONF-09** | **Medium** | **`app_self_assessment.py` (বিকল্প entry point) দুর্বল:** CSRF init নেই, প্রোডাকশনেও SQLite fallback, error handler রেজিস্টার নেই, `SESSION_COOKIE_SECURE` কেবল `'true'` স্ট্রিং মানে। | `app_self_assessment.py:29-57` |
| **CONF-10** | **Medium** | **Docker:** `Dockerfile` root user, `COPY .` (লোকাল `.env`/DB ইমেজে ঢুকতে পারে), unpinned base; `docker-compose.prod.yml`-এ `SECRET_KEY` fallback `your-secret-key-here`; `nginx.conf`-এ `server_tokens off`/`client_max_body_size` নেই, CSP-তে `'unsafe-inline' http:`। | `Dockerfile`, `Dockerfile.prod`, `docker-compose.prod.yml`, `nginx.conf:59` |
| **CONF-11** | **Medium** | `app.py` main block: `allow_unsafe_werkzeug=True`, `0.0.0.0` bind (`ALLOW_NETWORK_ACCESS`), Werkzeug dev server — ভুলে প্রোডাকশনে চললে বিপজ্জনক। | `app.py:18600-18724`; `launch_app.py`; `run_app.sh`; `start_network.sh` |
| **CONF-12** | **Low** | ডকুমেন্টেশনে (৬০+ `.md`) cPanel username (`gronthon`, `kulawams`), home path, DB নাম (`gronthon_ams2`), SMTP host — reconnaissance-এ সহায়ক। | `*.md`, `scripts/sql/ADD_YEAR_TERM_COLUMNS.sql:7` |
| **CONF-13** | **Info** | ভালো: `resolve_secret_key()` প্রোডাকশনে দুর্বল key প্রত্যাখ্যান; `DATABASE_URL` না থাকলে SQLite প্রত্যাখ্যান; `TRUST_PROXY_HOPS` সীমিত; git ইতিহাসে `.env`/`.db` কখনো কমিট হয়নি। | `utils/security_config.py`; `app.py:260-266` |

### ৩.৬ লগিং, error handling, ডিবাগ অবশেষ (LOG)

| ID | Severity | সমস্যা | অবস্থান |
|---|---|---|---|
| **LOG-01** | **Medium** | **Exception বার্তা ক্লায়েন্টে ফেরত (`str(e)`) ১১০+ জায়গায়** (`jsonify({'error': str(e)})`, `flash(f'… {str(e)}')`) → SQL/টেবিল/পাথ/লাইব্রেরি ভার্সন ফাঁস। (কেন্দ্রীয় 500-handler redacted — ভালো; কিন্তু এই try/except-গুলো তা বাইপাস করে।) | `blueprints/class_management/routes.py` (৪৯), `app.py` (৩০), `result_management` (১৩), `routine_management` (৬), অন্যান্য |
| **LOG-02** | **Medium** | **Cursor ডিবাগ লগ কোডে রয়ে গেছে:** ডেভেলপার মেশিনের absolute path `/Users/isckra/…/.cursor/debug.log`-এ **ছাত্রের ID, Part A/B নম্বর, সেশন মেটাডেটা** append করা হয়। প্রোডাকশনে path না থাকায় exception → `try/except` না থাকলে রিকোয়েস্ট ফেল (কিছু জায়গায় নিরাপদ, কিছু জায়গায় নয়); ডেভ মেশিনে PII জমে। | `blueprints/result_management/routes.py:2444-3146` (২৫+ জায়গা); `app.py:2994-3037` |
| **LOG-03** | **Medium** | **Request-time `db.create_all()` / schema mutation** — HTTP রিকোয়েস্টের ভেতরে DDL; race condition, অনিয়ন্ত্রিত schema drift, migration bypass। | `app.py:18600`; `blueprints/academic_calendar/routes.py:238, 488, 688`; `blueprints/class_management/routes.py:4773, 4781, 4822` |
| **LOG-04** | **Medium** | **লগ ডিরেক্টরি ডিফল্টে অ্যাপের ভেতরে (`logs/`)** — `AMS_LOG_DIR` না দিলে docroot-এ (CONF-01 দেখুন); লোকাল `logs/app_errors.log.1` ৩৮ MB, `detailed_errors.log`-এ full traceback+URL (query string-এ token থাকতে পারে)। কোনো log-rotation policy নেই passenger_wsgi-র handler-এ। | `error_handler.py:40-50`; `passenger_wsgi.py:29-48`; `logs/` |
| **LOG-05** | **Medium** | **প্রজেক্ট ফোল্ডারে সংবেদনশীল ডেটা:** `tmp/` (৩৯ ফাইল: ছাত্রদের নম্বরের CSV, SQL restore স্ক্রিপ্ট), `instance/academic_management.db` + ২টি backup, `uploads/question_bank/*.pdf`, ৫০ MB লগ। git-ignored হলেও ব্যাকআপ/জিপ/cPanel upload-এ চলে যেতে পারে (CONF-01)। | `tmp/`, `instance/`, `logs/` |
| **LOG-06** | **Low** | `print()`/`traceback.print_exc()` stderr-এ (Passenger লগে মিশে যায়); `current_app.logger.debug` লগইন-রোল লগ। | `blueprints/auth/routes.py:560-561`; `routine_management/routes.py:3727` |
| **LOG-07** | **Info** | ভালো: `error_handler.create_error_response` কোনো traceback ফেরত দেয় না; request body/পাসওয়ার্ড লগ হয় না; `audit_log` UI থেকে মোছা যায় না। | `error_handler.py:437-471` |

### ৩.৭ সিকিউরিটি হেডার ও ট্রান্সপোর্ট (HDR)

| ID | Severity | সমস্যা | অবস্থান |
|---|---|---|---|
| **HDR-01** | **Medium** | **গ্লোবাল সিকিউরিটি হেডার নেই:** কোনো `after_request` নেই; `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` কেবল কয়েকটি PDF-response-এ। লাইভ `.htaccess`-এ কেবল HSTS। → clickjacking, INJ-01/02-এর প্রভাব বৃদ্ধি। | `app.py` (অনুপস্থিত); `.htaccess`; `nginx.conf:55-59` |
| **HDR-02** | **Medium** | `SESSION_COOKIE_SECURE` env-নির্ভর (ডিফল্ট false); `PERMANENT_SESSION_LIFETIME` ১২ ঘণ্টা + `SESSION_REFRESH_EACH_REQUEST` → কার্যত অসীম sliding session; কোনো absolute timeout/idle logout নেই; server-side session revocation নেই (signed cookie — পাসওয়ার্ড বদলালেও পুরনো cookie বৈধ থাকে)। | `app.py:233-239`; `utils/security_config.py:56-64` |
| **HDR-03** | **Low** | HSTS-এ `preload` নেই; `.htaccess`-এ HTTP→HTTPS redirect নেই (cPanel-এ আলাদা ভাবে থাকতে পারে — নিশ্চিত করতে হবে)। | `.htaccess:13` |

### ৩.৮ ডিপেন্ডেন্সি CVE (DEP) — OSV.dev স্ক্যান, ৩১টি pinned প্যাকেজ

| প্যাকেজ (pinned) | Advisory (উল্লেখযোগ্য) | Severity | Fix version |
|---|---|---|---|
| **Pillow 10.1.0** | CVE-2023-50447 **Arbitrary Code Execution** (Critical); CVE-2024-28219 buffer overflow; ১৪+ HIGH (decompression-bomb bypass, heap OOB write, DoS) | **Critical** | ≥ 12.3.0 |
| **PyMySQL 1.1.0** | CVE-2024-36039 **SQL Injection** (Critical, JSON escaping) | **Critical** | ≥ 1.1.1 |
| **Werkzeug 2.3.8** | CVE-2024-34069 debugger RCE (High); CVE-2024-49767 multipart resource exhaustion; ৪× `safe_join` Windows | **High** | ≥ 3.1.6 |
| **gunicorn 21.2.0** | CVE-2024-1135, CVE-2024-6827 **HTTP request smuggling** (High) | **High** | ≥ 22.0.0 (23.x) |
| **cryptography 41.0.7** | CVE-2023-50782 Bleichenbacher oracle; CVE-2024-26130; CVE-2026-26007; CVE-2026-69249; vulnerable bundled OpenSSL ×2 | **High** | ≥ 49.0.0 |
| **weasyprint 52.5** | CVE-2025-68616 **SSRF bypass via redirect** (High); CVE-2026-49452 CSS injection | **High** | ≥ 68.0 (cPanel Pango সীমাবদ্ধতা — বিকল্প: ইনপুট HTML-এ `url()`/`<img src=http>` নিষিদ্ধ করা, `url_fetcher` allowlist) |
| **python-socketio 5.10.0** | CVE-2025-61765 pickle RCE (message-queue ব্যবহারে); CVE-2026-48804 binary attachment DoS (High) | **High** | ≥ 5.16.2 |
| **Jinja2 3.1.2** | CVE-2024-22195, CVE-2024-34064 (`xmlattr`), CVE-2024-56201, CVE-2024-56326, CVE-2025-27516 sandbox breakout | **Medium** | ≥ 3.1.6 |
| **eventlet 0.33.3** | CVE-2023-29483 DNS DoS; CVE-2025-58068 request smuggling | **Medium** | ≥ 0.40.3 (বা eventlet বাদ) |
| **python-dotenv 1.0.0** | CVE-2026-28684 symlink overwrite (`set_key`) | **Medium** | ≥ 1.2.2 |
| **Flask 2.3.3** | CVE-2026-27205 `Vary: Cookie` (Low) | Low | ≥ 3.1.3 |
| **click 8.1.7** | PYSEC-2026-2132 | Low | latest |
| Flask-Login 0.6.3, Flask-WTF 1.1.1, SQLAlchemy 2.0.21, alembic 1.12.0, reportlab 4.0.7, openpyxl, python-docx, PyYAML 6.0.1, itsdangerous 2.1.2 | কোনো open advisory নেই (তবে অনেক পুরনো) | Info | latest |

> `numpy`, `pandas`, `pypdfium2`, `uharfbuzz`, `fonttools`, `psycopg2-binary`, `certifi`, `brotlicffi` unpinned (`>=`) — reproducible build নয়; একটি lock file (`pip-compile`/`uv lock`) দরকার। `docs/security/requirements.lock.txt` আছে কিন্তু পুরনো (Werkzeug 2.3.7, Pillow 10.0.1) ও `requirements.txt`-এর সাথে অসঙ্গত।

---

## ৪. আক্রমণ-চেইন (কেন এগুলো একসাথে বিপজ্জনক)

1. **অ্যানোনিমাস → অ্যাডমিন:** ভিকটিম অ্যাডমিনের ইমেইল (ডকুমেন্টেশন/ফিশিং থেকে) → AUTH-01 (০.০৪ সেকেন্ডে কোড) → অ্যাডমিন অ্যাকাউন্ট → সব ছাত্রের ফলাফল/PII, AI key, `login_as` দিয়ে সবার অ্যাকাউন্ট।
2. **ছাত্র (TA) → অন্য ক্লাসের নম্বর/উপস্থিতি:** AUTHZ-08 + AUTHZ-03/04 → অন্য শিক্ষকের ক্লাসের ছাত্র মুছা/বদল; AUTHZ-07 দিয়ে নাম বদলে external teacher-এর সেশন দখল।
3. **শিক্ষক → অ্যাডমিন:** INJ-01 (নোটিসে `<script>`) → অ্যাডমিন দেখলে JS দিয়ে `admin_create_user`/`admin_reset_password` (AUTH-02: CSRF নেই, তাছাড়া same-origin) → অ্যাডমিন।
4. **নেটওয়ার্ক MITM → সার্ভার:** CONF-02 (`verify=False`) → cPanel পাসওয়ার্ড → সম্পূর্ণ hosting account।
5. **Passenger ডাউন/মিসকনফিগ → সোর্স ও DB ডাউনলোড:** CONF-01।

---

## ৫. প্রোডাকশন-রেডি করার রোডম্যাপ

### Phase 0 — এখনই (২৪–৭২ ঘণ্টা): রক্তক্ষরণ বন্ধ

| # | কাজ | ইস্যু |
|---|---|---|
| 0.1 | **পাসওয়ার্ড-রিসেট ফ্লো পুনর্গঠন:** কোড-হ্যাশ ক্লায়েন্টকে **কখনো** পাঠাবেন না। সার্ভার-সাইড টেবিলে (`password_reset_code`: user_id, `sha256(code+random_salt)`, expires_at, attempts, used_at) রাখুন; ক্লায়েন্টকে কেবল একটি opaque request-id দিন; **প্রতি request-এ সর্বোচ্চ ৫ চেষ্টা**, তারপর invalidate; ব্যবহারের পর one-time; আরও ভালো — ৬ ডিজিটের বদলে `secrets.token_urlsafe(32)` লিংক + ১৫ মিনিট মেয়াদ। সব বিদ্যমান challenge অকার্যকর করতে `RESET_CODE_SALT` বদলান। | AUTH-01 |
| 0.2 | **`CSRF_ENABLED=true`** প্রোডাকশন env-এ সেট করুন এবং কোডে ডিফল্ট `true` করুন; `WTF_CSRF_TIME_LIMIT` সসীম (যেমন ৮ ঘণ্টা) করে autosave পেজে টোকেন refresh endpoint দিন; অ্যাডমিশন POST থেকে `@csrf.exempt` সরিয়ে টেমপ্লেটে `csrf_token()` যোগ করুন; `/logout` POST করুন। | AUTH-02, AUTH-09 |
| 0.3 | **Routine Management-এ auth:** blueprint-এ `@routine_management_bp.before_request` দিয়ে `login_required` + role gate (`admin/head/officer` — mutation; staff — read); ছয়টি রুটে সরাসরি `@login_and_role_required(...)`। | AUTHZ-01, 02 |
| 0.4 | **Class Management ownership:** একটি helper `_require_session_access(session)` (admin/head/dean অথবা `user_owns_class_session`) তৈরি করে `edit_student`, `delete_student`, `add_student`, `upload_students`, `archive/unarchive_session`, `edit_session`, `course-assessment`, `students`, `evaluation`-এ প্রয়োগ; `ClassStudent` লোড করে তার `session`-এর উপর check। | AUTHZ-03, 04, 10 |
| 0.5 | **Result Management:** `_get_rstudent_or_404`/`_get_rsubject_or_404`-এর ভেতরে (বা প্রতিটি রুটে) `_can_access_session(parent_session)` না হলে `abort(403)`; সব download রুটে একই। | AUTHZ-05 |
| 0.6 | **Noticeboard sanitizer:** সেভ ও রেন্ডার দুই জায়গায় `sanitize_outline_html()` (বা `nh3`/`bleach` allowlist) দিয়ে `body_html` পরিশোধন; PDF-এও। বিদ্যমান নোটিসগুলো একবার migration দিয়ে sanitize করুন। | INJ-01 |
| 0.7 | **`.htaccess` হার্ডেনিং** (`scripts/security/htaccess_archive/.htaccess.kulawams.fixed` ভিত্তি করে; নিচের snippet দেখুন): `Options -Indexes`; সংবেদনশীল extension-এ (env, py, pyc, db, sqlite, log, md, sql, csv, zip, bak, ini, yaml, yml, txt, sh, lock) `Require all denied`; `.git` → 404; `instance/`, `logs/`, `tmp/`, `migrations/`, `scripts/`, `tests/`, `uploads/` ডিরেক্টরি deny। **স্থায়ী সমাধান:** অ্যাপ `~/ams_app/`-এ সরিয়ে `PassengerAppRoot` সেখানে দিন, `public_html`-এ কেবল `passenger_wsgi.py` stub + `static/`। | CONF-01 |
| 0.8 | **সার্ভারে docroot পরিষ্কার:** `.env`, `instance/*.db`, `logs/`, `tmp/`, `*.md`, `venv*`, zip, `reset_*`/`clear_*`/`create_admin.py` — `public_html` থেকে সরান (`scripts/security/docroot_cleanup.md` অনুসরণ); `AMS_LOG_DIR=/home/<user>/ams_logs` নিশ্চিত করুন। | CONF-01, LOG-04/05 |
| 0.9 | **সিক্রেট রোটেশন:** OpenAI key (`.env`), `SECRET_KEY` (সব সেশন invalidate হবে — AUTH-01 আক্রান্ত হয়ে থাকলে জরুরি), cPanel পাসওয়ার্ড (CONF-02-এর কারণে), SMTP পাসওয়ার্ড; `AI_KEY_ENCRYPTION_SECRET` সেট করে `scripts/security/reencrypt_ai_keys.py` চালান। | CONF-04, 08, 02 |
| 0.10 | **CI ঠিক করুন বা বন্ধ রাখুন:** `verify=False` সরান; পাসওয়ার্ডের বদলে SSH deploy key; ডিপ্লয় টার্গেট docroot-এর বাইরে; artifact থেকে `create_admin.py`, `reset_*` বাদ; `requirements_cpanel.txt` → `requirements.txt`; Action-গুলো commit-SHA দিয়ে pin। | CONF-02, 03 |
| 0.11 | **`reset_database_complete.py`-এর `admin123` সরান** (env/getpass থেকে নিন); ধ্বংসাত্মক স্ক্রিপ্টগুলো `scripts/dev/`-এ সরিয়ে `if os.getenv('FLASK_ENV')=='production': sys.exit()` গার্ড দিন। প্রোডাকশন DB-তে `admin` username-এর কোনো অ্যাকাউন্ট আছে কি না **এখনই চেক করুন**। | CONF-05 |
| 0.12 | **ডিপেন্ডেন্সি আপগ্রেড (অন্তত):** `Pillow>=12.3`, `PyMySQL>=1.1.1`, `Werkzeug>=3.1.6`+`Flask>=3.1`, `gunicorn>=23`, `cryptography>=49`, `python-socketio>=5.16.2`+`flask-socketio` সাম্প্রতিক, `Jinja2>=3.1.6`, `python-dotenv>=1.2.2`; staging-এ regression test (`pytest tests/`) চালান। WeasyPrint-এ cPanel Pango সীমাবদ্ধতা থাকলে অন্তত custom `url_fetcher` দিয়ে সব external URL block করুন। | DEP |

**০.৭-এর জন্য `.htaccess` snippet** (Passenger ব্লকের নিচে যোগ করুন; অ্যাপ docroot-এর বাইরে সরানো পর্যন্ত অন্তর্বর্তী সুরক্ষা):

```apache
Options -Indexes -MultiViews

# সোর্স, কনফিগ, ডেটা, লগ, ডকুমেন্টেশন — কখনো সরাসরি সার্ভ হবে না
<FilesMatch "\.(env|py|pyc|pyo|db|sqlite|sqlite3|log|md|sql|csv|zip|bak|ini|cfg|yaml|yml|txt|sh|lock|pid|json)$">
    Require all denied
</FilesMatch>
<FilesMatch "^(\.env.*|\.git.*|\.htaccess|passenger_wsgi\.py|requirements.*|Dockerfile.*|docker-compose.*)$">
    Require all denied
</FilesMatch>

# ডিরেক্টরি-স্তরের deny (public_html-এর ভেতরে থাকলে)
RedirectMatch 404 ^/\.git(/|$)
RedirectMatch 404 ^/(instance|logs|tmp|migrations|scripts|tests|docs|blueprints|utils|tenants|uploads|venv[^/]*|\.venv[^/]*)(/|$)
RedirectMatch 404 ^/static/uploads/(user_photos|user_signatures|admission_exam)(/|$)

<IfModule mod_headers.c>
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "DENY"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
    Header always set Permissions-Policy "camera=(), microphone=(), geolocation=()"
</IfModule>
```

> `static/manifest.json` ও `static/sw.js` অ্যাপ-রুট (`/manifest.json`, `/sw.js`) দিয়ে সার্ভ হয়, তাই `json` deny-তে সমস্যা হওয়ার কথা নয়; staging-এ PWA install ও `/static/` অ্যাসেট লোড পরীক্ষা করে নিন। `static/uploads/*` deny করার আগে Phase 1.5 (authenticated serving) সম্পন্ন করুন, না হলে ছবি দেখাবে না।

### Phase 1 — ১–২ সপ্তাহ: High ইস্যু ও abuse-প্রতিরোধ

| # | কাজ | ইস্যু |
|---|---|---|
| 1.1 | **Rate limiting:** `Flask-Limiter` (storage: DB/Redis/memcached — in-memory নয়, Passenger multi-process) — `/login` (IP ৩০/মিনিট + username ১০/১৫মিনিট), `/forgot-password` (IP ৫/ঘণ্টা, email ৩/ঘণ্টা), `/account/verify-code`, `/reset-password/*`, `/apply/<token>/login` (IP ২০/ঘণ্টা + application_id ৫/১৫মিনিট, তারপর lockout), `/feedback/<code>`, AI endpoints, PDF export। login throttle-এ global per-username lock ও fail-**closed** বিকল্প (অথবা অন্তত alert)। | AUTH-03, 04, 05 |
| 1.2 | **`has_role()` ঠিক করুন:** কেবল `get_effective_roles(user)` (active_role) দেখুন; `is_admin`, `has_teacher_privileges`, `has_staff_privileges`, `role_required` — সব এক মডেলে আনুন। `role_required`-এর `is_admin(...) or has_role(...)` শর্টকাট রাখতে হলে সেটিও effective role-ভিত্তিক হোক। `tests/`-এ multi-role down-scoping-এর টেস্ট যোগ করুন। | AUTHZ-06 |
| 1.3 | **Teaching Assistant প্রিভিলেজ সংকোচন:** TA-কে `TEACHING_ROLES` থেকে আলাদা করে কেবল নির্দিষ্ট রুটে (attendance-take, marks-entry — এবং কেবল যেই সেশনে TA হিসেবে নিযুক্ত) অনুমতি দিন; নোটিস কম্পোজ, সেশন তৈরি/সম্পাদনা, evaluator invite থেকে বাদ। | AUTHZ-08 |
| 1.4 | **নাম-ভিত্তিক identity বাদ:** `resolve_caller_teacher()` ও `_ensure_current_teacher()` থেকে `Teacher.name == full_name` fallback সরান; সব User↔Teacher লিঙ্ক `teacher_id` দিয়ে (একবার migration script দিয়ে backfill — `scripts/security/backfill_teacher_id.sql` আছে); `Teacher.name`-এ unique constraint; প্রোফাইলে নাম-লক সব non-admin-এর জন্য। | AUTHZ-07 |
| 1.5 | **আপলোড `static/` থেকে বাইরে:** `user_photos`, `user_signatures`, `admission_exam/cycle_*` → `~/ams_private_uploads/` (docroot-এর বাইরে; `PRIVATE_UPLOAD_DIR` env); সার্ভ করুন কেবল authenticated রুট দিয়ে (`send_confined_file`) — ছবি: নিজে/অ্যাডমিন/হেড; স্বাক্ষর: নিজে/অ্যাডমিন; প্রার্থী ফাইল: `@candidate_required` বা স্টাফ। DB-তে থাকা পুরনো `/static/uploads/...` path migration দিয়ে বদলান। ফাইলনামে timestamp-এর বদলে `secrets.token_urlsafe(16)`। | FILE-01, 02 |
| 1.6 | **আপলোড validation একীভূত করুন:** একটি `utils/uploads.py` — extension allowlist (per-purpose), magic-byte (`python-magic`/`filetype`) যাচাই, ছবিতে Pillow re-encode + `Image.MAX_IMAGE_PIXELS`, PDF-এ `%PDF-` header + page-count সীমা, সাইজ সীমা; Q&A attachment ও প্রার্থী-সনদে প্রয়োগ; landing attachment থেকে `zip/rar/exe` বাদ; ডাউনলোডে সর্বদা `Content-Disposition: attachment` + `X-Content-Type-Options: nosniff`। | FILE-03, 04, 05 |
| 1.7 | **Redirect ও SSRF:** `redirect(request.referrer …)` → `_safe_next_url(request.referrer)` অথবা নির্দিষ্ট `url_for`; AI `api_base_url`-এ `https://` বাধ্যতামূলক + প্রোভাইডার-হোস্ট allowlist (`api.openai.com`, `generativelanguage.googleapis.com`, `api.anthropic.com`, `api.deepseek.com`) + DNS resolve করে private/loopback/link-local IP ব্লক (redirect follow বন্ধ)। | INJ-03, 04 |
| 1.8 | **ইমেইল ও হেডার:** সব ইমেইল ইনপুটে `email_validator.validate_email()`; `\r\n` থাকলে reject; `Content-Disposition` filename-এ `secure_filename` + `filename*` RFC 5987; `Header()` দিয়ে `To`। | INJ-05, 06 |
| 1.9 | **DOM XSS:** `exam_committee_chief/dashboard.html`-এ `member.*` → `textContent` বা escape helper; সব `innerHTML` ব্যবহারে code-review (grep `innerHTML =`), API থেকে আসা স্ট্রিং escape। | INJ-02 |
| 1.10 | **Socket.IO scope:** গ্লোবাল broadcast (`session_created`, `result_updated`, `routine_updated`, `course_updated`, `student_updated`) → role/room-ভিত্তিক (`join_room('staff')`, `room=f'user_{id}'`); payload-এ কেবল id/ন্যূনতম মেটাডেটা। | AUTHZ-09 |
| 1.11 | **সিক্রেট-হাইজিন ও git:** `git rm --cached cpanel_deployment.zip venv_test venv_feedback "static/uploads/user_photos/*" ".git 2"`; `.gitignore`-এ `*.zip`, `venv*/`, `static/uploads/`; পুশ হয়ে থাকলে `git filter-repo` দিয়ে ইতিহাস purge + সব collaborator re-clone; `gitleaks`/`trufflehog` pre-commit hook। | CONF-06 |
| 1.12 | **SMTP TLS:** প্রোডাকশনে `MAIL_SSL_VERIFY=True` (হোস্টের CA bundle ঠিক থাকলে `certifi` দিয়ে); `MAIL_USE_SENDMAIL` ডিফল্ট `False`; হোস্ট যদি সার্টিফিকেট ঠিক না করে, তবে অন্তত pinned fingerprint। | CONF-07 |

### Phase 2 — ২–৪ সপ্তাহ: Medium ইস্যু ও hardening

| # | কাজ | ইস্যু |
|---|---|---|
| 2.1 | **গ্লোবাল সিকিউরিটি হেডার** (`@app.after_request` বা `Flask-Talisman`): `Content-Security-Policy` (শুরুতে `Report-Only`, তারপর enforce; inline script-এ nonce), `X-Frame-Options: DENY` (PDF iframe লাগলে `SAMEORIGIN`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`, `Cache-Control: no-store` সব authenticated HTML-এ; HSTS-এ `preload` (ডোমেইন submit করে)। | HDR-01, 03 |
| 2.2 | **সেশন হার্ডেনিং:** `SESSION_COOKIE_SECURE` প্রোডাকশনে বাধ্যতামূলক `True` (`is_production()` হলে override); absolute lifetime (যেমন ১২ ঘণ্টা, refresh নির্বিশেষে) + idle timeout (৩০–৬০ মিনিট); পাসওয়ার্ড বদলালে/অ্যাডমিন reset করলে পুরনো সেশন invalidate — `User.session_version` কলাম যোগ করে `user_loader`-এ যাচাই (Flask-Login `get_id()` = `f"{id}:{session_version}"`); `Flask-Session` (server-side, DB/Redis) বিবেচনা। | HDR-02 |
| 2.3 | **Exception বার্তা ক্লায়েন্টে না পাঠানো:** ১১০+ `str(e)` জায়গায় generic বার্তা + `current_app.logger.exception()` + error-id (correlation id) ক্লায়েন্টে; একটি helper `api_error(exc, public_msg)` তৈরি করুন; `rg "str\(e\)"` দিয়ে CI-তে lint। | LOG-01 |
| 2.4 | **ডিবাগ অবশেষ সরানো:** `.cursor/debug.log` লেখার ২৫+ ব্লক (result_management 2444–3146, app.py 2994–3037) সম্পূর্ণ মুছুন; `print()`/`traceback.print_exc()` → logger; ngrok লজিক সরান; `/test_download` রুট বাদ। | LOG-02, 06 |
| 2.5 | **Schema management:** request-time `db.create_all()`/`ALTER` সরিয়ে Alembic migration (`flask db upgrade`) ডিপ্লয়ের একটি ধাপ করুন; migration head একটাই রাখুন; রুট-লেভেলের `add_*_columns.py`/`fix_*.py` স্ক্রিপ্ট `scripts/legacy/`-এ সরান। | LOG-03 |
| 2.6 | **লগ:** `AMS_LOG_DIR` docroot-এর বাইরে বাধ্যতামূলক; `passenger_wsgi.py`-এর `FileHandler` → `RotatingFileHandler`; লগে query-string মাস্ক (token/code); লগ ফাইলে `0600` permission; ৯০ দিন retention। | LOG-04 |
| 2.7 | **প্রজেক্ট ফোল্ডার পরিষ্কার:** `tmp/` (ছাত্রের নম্বরের CSV), `instance/*.db*`, ৫০ MB লগ, `blueprints/class_management/routes.py.bak`, দুটি zip, তিনটি অতিরিক্ত venv — ডেভ মেশিন থেকেও সরান/এনক্রিপ্টেড ব্যাকআপে রাখুন; ভবিষ্যতে export-গুলো `~/exports/`-এ (রিপোর বাইরে)। | LOG-05, CONF-06 |
| 2.8 | **পাসওয়ার্ড নীতি:** ন্যূনতম ১০ অক্ষর (student ৮), common-password blocklist (`zxcvbn`/HIBP k-anonymity), username/ইমেইলের অংশ নিষিদ্ধ; সব ৪ জায়গায় (`profile`, admin create/reset, verify-code, account-access) একটি `validate_password()` helper। | AUTH-06, 07 |
| 2.9 | **User enumeration ও logout:** forgot-password-এ সব ক্ষেত্রে একই বার্তা ও একই redirect (ইমেইল পাঠানো ব্যাকগ্রাউন্ডে/asynchronously); `/logout` POST + CSRF। | AUTH-08, 09 |
| 2.10 | **অডিট সম্প্রসারণ:** `auth.login.success/failure/lockout`, `auth.logout`, `auth.impersonate.start/stop` (impersonator_id সহ), `auth.password_reset.request/complete`, `admin.ai_settings.update`, ফাইল আপলোড/ডিলিট, session archive/delete, bulk import; অ্যাডমিন UI-তে export; DB-user-এর `DELETE` privilege না থাকলে আরও ভালো (append-only)। | AUTH-10 |
| 2.11 | **`app_self_assessment.py`:** `csrf.init_app`, `register_error_handlers`, প্রোডাকশনে SQLite প্রত্যাখ্যান, `SESSION_COOKIE_SECURE` parsing — মূল `create_app`-এর সাথে একই কনফিগ helper ব্যবহার করুন (কোড ডুপ্লিকেশন বাদ)। | CONF-09 |
| 2.12 | **Docker/nginx (যদি ব্যবহার হয়):** non-root user, `COPY` allowlist (`.dockerignore`-এ `.env`, `instance`, `logs`, `tmp`, `venv*`, `*.zip`), base image digest-pin, `server_tokens off`, `client_max_body_size 16m`, CSP nonce-ভিত্তিক; `docker-compose.prod.yml`-এ `SECRET_KEY` fallback সরান (`${SECRET_KEY:?required}`)। | CONF-10 |
| 2.13 | **Dev-server escape hatch:** `app.py` `__main__` ব্লক থেকে `allow_unsafe_werkzeug=True` সরান বা `if is_production(): sys.exit('use gunicorn')`; প্রোডাকশন WSGI: gunicorn (`--worker-class gthread` বা eventlet-এর বদলে `gevent`/uvicorn-worker) অথবা Passenger। | CONF-11 |
| 2.14 | **LIKE wildcard escape** ও search-এ দৈর্ঘ্য সীমা; pagination বাধ্যতামূলক। | INJ-07 |
| 2.15 | **ডকুমেন্টেশন পরিচ্ছন্নতা:** ৬০+ deployment `.md` → `docs/ops/` (রিপো পাবলিক হলে username/path/DB-নাম মাস্ক); রুট থেকে সরান যাতে docroot-এ না যায়। | CONF-12 |

### Phase 3 — চলমান প্রক্রিয়া (production-grade operations)

| ক্ষেত্র | কাজ |
|---|---|
| **Dependency management** | `requirements.txt` → `pip-compile`/`uv` lock file (hash-pinned); CI-তে `pip-audit` (fail on High+); মাসিক আপগ্রেড উইন্ডো; Dependabot/Renovate। |
| **CI/CD গেট** | প্রতি PR-এ: `pytest`, `bandit -r . -x venv*`, `pip-audit`, `gitleaks`, `ruff`; deploy কেবল protected branch থেকে, manual approval; artifact SBOM। |
| **টেস্ট কভারেজ (security)** | এই রিপোর্টের প্রতিটি Critical/High-এর জন্য regression test: anonymous → routine routes 302/401; teacher-B → teacher-A-এর `edit_student` 403; tabulator cross-session 403; reset-code brute-force 429/lock; notice `<script>` sanitized; static upload path 404/401; `has_role` active_role নিয়ে। বিদ্যমান `tests/test_smoke_*.py`-এর ধাঁচে। |
| **সিক্রেট ম্যানেজমেন্ট** | সব সিক্রেট কেবল env (cPanel Python App → Environment Variables); ত্রৈমাসিক রোটেশন; `SECRET_KEY` ≥ ৬৪ random bytes; আলাদা `AI_KEY_ENCRYPTION_SECRET`; কখনো `.env` সার্ভারে docroot-এ না। |
| **ব্যাকআপ ও রিকভারি** | দৈনিক MySQL dump (এনক্রিপ্টেড, off-server), আপলোড ডিরেক্টরি sync, ৩০ দিন retention; ত্রৈমাসিক restore drill; migration-এর আগে snapshot। |
| **মনিটরিং ও অ্যালার্ট** | error-rate/5xx, login failure spike, lockout count, forgot-password volume, disk usage, SMTP failure — অ্যালার্ট (ইমেইল/Telegram); uptime monitor; লগে PII মাস্ক। |
| **অ্যাক্সেস কন্ট্রোল প্রক্রিয়া** | অ্যাডমিন অ্যাকাউন্ট ন্যূনতম (২–৩), প্রত্যেকের আলাদা অ্যাকাউন্ট, `admin` username নিষিদ্ধ; সেমিস্টার শেষে account review (প্রাক্তন শিক্ষক/ছাত্র নিষ্ক্রিয়); `login_as` ব্যবহারে অডিট রিভিউ; ভবিষ্যতে অ্যাডমিনে TOTP 2FA (`pyotp`)। |
| **ডেটা সুরক্ষা** | ছাত্রের নম্বর/PII data-classification; export-এ watermark/অডিট; retention policy (অ্যাডমিশন প্রার্থীর ডকুমেন্ট ফলাফল প্রকাশের N মাস পর মুছা); privacy notice। |
| **Incident response** | কার সাথে যোগাযোগ, কীভাবে সব সেশন invalidate (`SECRET_KEY` রোটেশন), কীভাবে DB restore, কীভাবে ব্যবহারকারীদের জানানো — এক পাতার runbook। |
| **পুনঃঅডিট** | Phase 0–1 শেষে authenticated dynamic test (OWASP ZAP/Burp) staging-এ; বছরে একবার পূর্ণ রিভিউ। |

---

## ৬. প্রোডাকশন Go-Live চেকলিস্ট

**Environment variables (cPanel Python App):**

- [ ] `FLASK_ENV=production`, `CPANEL=1`
- [ ] `SECRET_KEY` = ≥৬৪ random অক্ষর (`python -c "import secrets;print(secrets.token_urlsafe(64))"`) — placeholder নয়
- [ ] `AI_KEY_ENCRYPTION_SECRET` = আলাদা random মান; `reencrypt_ai_keys.py` চালানো
- [ ] `DATABASE_URL=mysql+pymysql://…` (আলাদা DB user, কেবল প্রয়োজনীয় privilege, `DROP` নেই)
- [ ] `CSRF_ENABLED=true`
- [ ] `SESSION_COOKIE_SECURE=true`, `SESSION_LIFETIME_HOURS=8` (বা কম)
- [ ] `TRUST_PROXY_HOPS=1` (cPanel Apache) — বেশি নয়
- [ ] `PUBLIC_APP_URL=https://<domain>`, `SOCKETIO_CORS_ORIGINS` নির্দিষ্ট (কখনো `*`)
- [ ] `MAIL_SSL_VERIFY=True`, `MAIL_USE_SENDMAIL=False`; SMTP পাসওয়ার্ড রোটেটেড
- [ ] `AMS_LOG_DIR=/home/<user>/ams_logs`; `PRIVATE_UPLOAD_DIR=/home/<user>/ams_uploads`
- [ ] `DEFAULT_STUDENT_PASSWORD` **সেট করা নেই** (random per-account)
- [ ] `OPENAI_API_KEY` env-এ নেই (AI key কেবল Admin → AI Settings, encrypted)

**সার্ভার/ফাইল সিস্টেম:**

- [ ] অ্যাপ কোড `public_html`-এর **বাইরে**; docroot-এ কেবল `passenger_wsgi.py` stub + `static/` (কোনো uploads নয়)
- [ ] `.htaccess`: `Options -Indexes` + FilesMatch deny + `.git` 404 (Phase 0.7)
- [ ] docroot-এ `.env`, `*.db`, `logs/`, `tmp/`, `*.md`, `venv*`, zip, `reset_*`/`clear_*`/`create_admin.py` নেই
- [ ] ফাইল permission: কোড `644/755`, `.env`/লগ `600`, uploads `700`
- [ ] HTTP→HTTPS redirect, বৈধ TLS সার্টিফিকেট, HSTS
- [ ] MySQL remote access বন্ধ; DB user host-restricted

**অ্যাপ্লিকেশন:**

- [ ] Phase 0-এর ১২টি কাজ সম্পন্ন ও staging-এ verified
- [ ] `pytest tests/` সবুজ + নতুন security regression test
- [ ] `pip-audit` — কোনো Critical/High নেই
- [ ] `admin`/`admin123` বা অন্য default অ্যাকাউন্ট নেই (`SELECT username FROM users WHERE role LIKE '%admin%'`)
- [ ] `must_change_password` সব নতুন অ্যাকাউন্টে; সব বিদ্যমান ব্যবহারকারীকে পাসওয়ার্ড বদলাতে বাধ্য করা (AUTH-01-এর কারণে) — এবং `SECRET_KEY` রোটেশনে সব সেশন invalidate
- [ ] `audit_log`, `login_throttle` টেবিল বিদ্যমান (`scripts/sql/add_audit_log.sql`, `phase3_security_schema.sql`)
- [ ] error page-এ traceback নেই (staging-এ `raise` করে দেখুন)

**অপারেশন:**

- [ ] ব্যাকআপ চালু ও restore পরীক্ষিত
- [ ] মনিটরিং/অ্যালার্ট চালু
- [ ] Incident runbook লিখিত; সিক্রেট রোটেশন ক্যালেন্ডার
- [ ] CI: TLS verify, SSH key, SHA-pinned actions, docroot-বহির্ভূত টার্গেট

---

## ৭. যাচাই-পদ্ধতি ও সীমাবদ্ধতা

- **যাচাইকৃত (কোড পড়ে ও/অথবা PoC):** AUTH-01 (অফলাইন PoC — `loads_unsafe` দিয়ে payload পড়া ও ১০ লক্ষ SHA-256 মিলিয়ে ০.০৪ সেকেন্ডে কোড উদ্ধার), AUTH-02, AUTH-03, AUTHZ-01–07, INJ-01, FILE-01/02, CONF-01–07, LOG-01–03, DEP (OSV API)।
- **স্ট্যাটিক রিভিউ থেকে অনুমিত (ম্যানুয়াল কনফার্মেশন দরকার):** cPanel-এ Apache আসলে `static/`-এর বাইরের ফাইল সরাসরি সার্ভ করছে কি না (Passenger config-নির্ভর); feedback/survey token endpoint-এ brute-force সম্ভাব্যতা; `username == student_id` collision; WeasyPrint SSRF বাস্তবে ট্রিগারযোগ্য কি না (input HTML-এ external URL ঢুকতে পারে কি না); Ghostscript-এর ভার্সন/CVE সার্ভারে; production DB-তে `admin` অ্যাকাউন্টের অস্তিত্ব।
- **স্কোপে নেই:** সার্ভার OS/Apache/MySQL কনফিগ, cPanel অ্যাকাউন্টের নিরাপত্তা (2FA), DNS/ইমেইল (SPF/DKIM/DMARC), ব্যবসায়িক লজিক (গ্রেড ক্যালকুলেশন সঠিকতা), পারফরম্যান্স।
- **পরিসংখ্যান:** ~৪৫০ HTTP রুট + ৬ Socket.IO হ্যান্ডলার পর্যালোচিত; ২৮টি রুটে কোনো auth decorator নেই, তার মধ্যে ৬টি অনিচ্ছাকৃত (Routine Management); `str(e)` ক্লায়েন্টে ১১০+ জায়গায়; ৩১টি pinned ডিপেন্ডেন্সিতে ~৯০ advisory (১৫টি প্যাকেজ আক্রান্ত)।

---

## ৮. সংশ্লিষ্ট ফাইলসূচি (দ্রুত রেফারেন্স)

| বিষয় | ফাইল |
|---|---|
| অ্যাপ কনফিগ, CSRF, session | `app.py:206-360`, `utils/security_config.py` |
| অথেনটিকেশন / রিসেট | `blueprints/auth/routes.py`, `utils/login_throttle.py`, `utils/request_ip.py` |
| রোল/অথরাইজেশন | `role_utils.py`, `utils/ownership.py`, `utils/window_utils.py` |
| Class Management IDOR | `blueprints/class_management/routes.py` (1680–1760, 3541, 4524–4680, 6889–6954, 10064–10121) |
| Result Management IDOR | `blueprints/result_management/routes.py` (1041–1101, 1604–1646, 2400–2427, 4642+) |
| Routine Management unauth | `blueprints/routine_management/routes.py` (1108–1200, 1836, 3161, 3729, 3791) |
| Noticeboard XSS | `blueprints/noticeboard/routes.py`, `audience.py`, `templates/noticeboard/detail.html`, `notice_pdf.html` |
| Admission portal | `blueprints/admission_exam/routes.py` (150–420, 3150–3600, 3832–3930) |
| আপলোড/স্টোরেজ | `utils/safe_files.py`, `utils/user_signature.py`, `app.py:18410-18478` |
| AI / SSRF / key | `utils/ai/client.py`, `utils/ai/encryption.py`, `app.py:3878-4041` |
| লগিং/এরর | `error_handler.py`, `utils/audit.py`, `passenger_wsgi.py` |
| ডিপ্লয়মেন্ট | `.htaccess`, `scripts/security/*`, `.github/workflows/*`, `Dockerfile*`, `docker-compose*.yml`, `nginx.conf` |
| ডিপেন্ডেন্সি | `requirements.txt`, `docs/security/requirements.lock.txt` |

*রিপোর্ট শেষ।*