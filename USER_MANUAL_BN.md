# 📖 Academic Management System - ইউজার ম্যানুয়াল

## সূচিপত্র

1. [সফটওয়্যার পরিচিতি](#সফটওয়্যার-পরিচিতি)
2. [প্রথম ব্যবহার](#প্রথম-ব্যবহার)
3. [লগইন সিস্টেম](#লগইন-সিস্টেম)
4. [অ্যাডমিন ড্যাশবোর্ড](#অ্যাডমিন-ড্যাশবোর্ড)
5. [ক্লাস ম্যানেজমেন্ট](#ক্লাস-ম্যানেজমেন্ট)
6. [কোর্স ম্যানেজমেন্ট](#কোর্স-ম্যানেজমেন্ট)
7. [স্টুডেন্ট ম্যানেজমেন্ট](#স্টুডেন্ট-ম্যানেজমেন্ট)
8. [রেজাল্ট ম্যানেজমেন্ট](#রেজাল্ট-ম্যানেজমেন্ট)
9. [রুটিন ম্যানেজমেন্ট](#রুটিন-ম্যানেজমেন্ট)
10. [প্রোফাইল ম্যানেজমেন্ট](#প্রোফাইল-ম্যানেজমেন্ট)
11. [সাধারণ সমস্যা সমাধান](#সাধারণ-সমস্যা-সমাধান)

---

## সফটওয়্যার পরিচিতি

**Academic Management System** একটি সম্পূর্ণ ওয়েব-ভিত্তিক একাডেমিক ব্যবস্থাপনা সিস্টেম যা শিক্ষাপ্রতিষ্ঠানের জন্য নিম্নলিখিত সুবিধা প্রদান করে:

- ✅ **ক্লাস ম্যানেজমেন্ট** - সেশন তৈরি, স্টুডেন্ট যোগ, উপস্থিতি নেওয়া, এসেসমেন্ট মার্কস দেওয়া
- ✅ **কোর্স ম্যানেজমেন্ট** - কারিকুলাম তৈরি, কোর্স ম্যানেজ, স্টুডেন্ট রেজিস্ট্রেশন
- ✅ **স্টুডেন্ট ম্যানেজমেন্ট** - স্টুডেন্ট তথ্য যোগ/সম্পাদনা, ব্যাচ ম্যানেজমেন্ট
- ✅ **রেজাল্ট ম্যানেজমেন্ট** - পরীক্ষার ফলাফল ইনপুট, রেজাল্ট ভিউ, আর্কাইভ
- ✅ **রুটিন ম্যানেজমেন্ট** - ক্লাস রুটিন তৈরি, শিক্ষক-কোর্স অ্যাসাইনমেন্ট
- ✅ **অ্যাডমিন প্যানেল** - ইউজার ম্যানেজমেন্ট, সিস্টেম কন্ট্রোল

---

## প্রথম ব্যবহার

### ১. সিস্টেমে প্রবেশ

1. আপনার ওয়েব ব্রাউজার খুলুন
2. সিস্টেমের URL-এ যান (যেমন: `https://kulawams.xyz`)
3. লগইন পেজে পৌঁছবেন

### ২. প্রথম লগইন

**অ্যাডমিন একাউন্ট:**
- অ্যাডমিন একাউন্ট শুধুমাত্র সিস্টেম অ্যাডমিন তৈরি করতে পারবেন
- প্রথম অ্যাডমিন একাউন্ট তৈরি করতে `create_admin.py` স্ক্রিপ্ট ব্যবহার করুন

**শিক্ষক একাউন্ট:**
- শিক্ষক একাউন্ট শুধুমাত্র অ্যাডমিন তৈরি করতে পারবেন
- নিজে থেকে রেজিস্ট্রেশন করা যাবে না

**স্টুডেন্ট একাউন্ট:**
- স্টুডেন্ট একাউন্ট অ্যাডমিন বা কোর্স কোঅর্ডিনেটর তৈরি করবেন
- ডিফল্ট পাসওয়ার্ড: `Student@123` (পরিবর্তন করা যাবে)

---

## লগইন সিস্টেম

### লগইন করার ধাপ

1. **Username** দিন (শিক্ষকের জন্য username, স্টুডেন্টের জন্য Student ID)
2. **Password** দিন
3. **"Sign in as"** ড্রপডাউন থেকে আপনার role নির্বাচন করুন:
   - Administrator (শুধু অ্যাডমিন)
   - Teacher (শিক্ষক)
   - Student (স্টুডেন্ট)
   - Head of Discipline (বিভাগীয় প্রধান)
   - Dean (ডিন)
   - Teaching Assistant (শিক্ষা সহায়ক)
   - Officer (কর্মকর্তা)

4. **"Sign In"** বাটনে ক্লিক করুন

### পাসওয়ার্ড ভুলে গেলে

1. লগইন পেজে **"Forgot Password?"** লিঙ্কে ক্লিক করুন
2. আপনার **Email** দিন
3. আপনার ইমেইলে পাসওয়ার্ড রিসেট লিঙ্ক পাঠানো হবে
4. লিঙ্কে ক্লিক করে নতুন পাসওয়ার্ড সেট করুন

### স্বয়ংক্রিয় Role নির্বাচন

- যদি আপনার username-এ **"28"** থাকে (যেমন: `242804`), তাহলে স্বয়ংক্রিয়ভাবে **"Student"** role নির্বাচিত হবে

---

## অ্যাডমিন ড্যাশবোর্ড

অ্যাডমিন হিসেবে লগইন করলে আপনি সম্পূর্ণ সিস্টেম নিয়ন্ত্রণ করতে পারবেন।

### প্রধান ফিচার

#### ১. User Management (ইউজার ম্যানেজমেন্ট)

**নতুন ইউজার তৈরি:**
1. **"Add New User"** বাটনে ক্লিক করুন
2. Modal-এ নিম্নলিখিত তথ্য দিন:
   - Username
   - Email
   - Full Name
   - Password & Confirm Password
   - Role/Category (এক বা একাধিক)
3. যদি **Teacher** role নির্বাচন করেন:
   - Designation (Professor, Associate Professor, Assistant Professor, Lecturer)
   - Institute
   - **Call Sign** (শিক্ষকের Call Sign)
   - **Bank Account No** (ব্যাংক একাউন্ট নম্বর)
4. **"Create User"** বাটনে ক্লিক করুন

**ইউজার সম্পাদনা:**
1. User Management টেবিলে **"Edit"** বাটনে ক্লিক করুন
2. তথ্য আপডেট করুন
3. **"Save Changes"** ক্লিক করুন

**পাসওয়ার্ড রিসেট:**
1. **"Reset Password"** বাটনে ক্লিক করুন
2. নতুন পাসওয়ার্ড দিন
3. **"Reset Password"** ক্লিক করুন

**ইউজার ডিলিট:**
1. **"Delete"** বাটনে ক্লিক করুন
2. Confirmation dialog-এ **"OK"** ক্লিক করুন

#### ২. Student Accounts (স্টুডেন্ট একাউন্ট)

স্টুডেন্ট একাউন্টগুলো আলাদা সেকশনে দেখানো হবে যেখানে:
- Student ID
- Name
- Email
- Batch
- Edit/Reset Password/Delete অপশন

#### ৩. User Role Privilege Management

**"User Role Privilege Management"** বাটনে ক্লিক করে বিভিন্ন role-এর privilege সেট করতে পারবেন।

---

## ক্লাস ম্যানেজমেন্ট

শিক্ষক হিসেবে ক্লাস ম্যানেজমেন্ট মডিউলে আপনি:

### ১. নতুন সেশন তৈরি

1. **"Create New Session"** বাটনে ক্লিক করুন
2. নিম্নলিখিত তথ্য দিন:
   - **Year** (First, Second, Third, Fourth, LLM)
   - **Term** (First, Second)
   - **Academic Session** (যেমন: 2024-2025)
   - **Course Code** (যেমন: 0421 28 Law 1101)
   - **Course Name** (যেমন: Jurisprudence)
   - **Course Type** (Theory/Sessional)
   - **Category** (UG/PG)
3. **"Create Session"** ক্লিক করুন

### ২. স্টুডেন্ট যোগ করা

**একক স্টুডেন্ট যোগ:**
1. Session-এ **"Add Students"** ক্লিক করুন
2. **"Add Student"** বাটনে ক্লিক করুন
3. Student ID এবং Name দিন
4. **"Add"** ক্লিক করুন

**Excel থেকে Bulk Upload:**
1. **"Upload Excel"** বাটনে ক্লিক করুন
2. Excel file select করুন (Student ID এবং Name columns থাকতে হবে)
3. **"Upload"** ক্লিক করুন

### ৩. উপস্থিতি নেওয়া

1. Session-এ **"Take Attendance"** ক্লিক করুন
2. তারিখ select করুন
3. উপস্থিত স্টুডেন্টদের checkbox tick করুন
4. **"Save Attendance"** ক্লিক করুন

**উপস্থিতি দেখতে:**
- **"View Attendance"** ক্লিক করুন
- প্রতিটি স্টুডেন্টের উপস্থিতি শতাংশ দেখতে পারবেন
- Excel/PDF হিসেবে ডাউনলোড করতে পারবেন

### ৪. এসেসমেন্ট মার্কস দেওয়া

1. Session-এ **"Assessment"** ক্লিক করুন
2. প্রতিটি স্টুডেন্টের জন্য:
   - **Assessment 1, 2, 3, 4** মার্কস দিন
   - **Absent** checkbox tick করুন (যদি absent হয়)
3. **"Save Marks"** ক্লিক করুন

**বিশেষ বৈশিষ্ট্য:**
- **Split Course** হলে: Part A শিক্ষক Assessment 1-2, Part B শিক্ষক Assessment 3-4 দেবেন
- অপর শিক্ষকের মার্কস **read-only** হিসেবে দেখাবে
- **Best 3 Total** (UG) বা **Total (40)** (PG) স্বয়ংক্রিয়ভাবে calculate হবে

**Assessment Reveal:**
- **"Reveal Assessment"** বাটনে ক্লিক করে স্টুডেন্টদের মার্কস দেখাতে পারবেন
- **"Hide Assessment"** দিয়ে আবার লুকিয়ে রাখতে পারবেন

### ৫. স্টুডেন্ট স্কোর দেখতে

1. **"Student View Scores"** মেনুতে যান
2. আপনার সব সেশন এবং স্টুডেন্টদের মার্কস দেখতে পারবেন

### ৬. Course Outline তৈরি

1. Session-এ **"Course Outline"** ক্লিক করুন
2. নিম্নলিখিত সেকশন পূরণ করুন:
   - **Course Objectives**
   - **Course Summary**
   - **Lesson Plan** (Weekly Schedule)
   - **Assessment Strategy**
   - **Learning Resources**
3. **"Save Outline"** ক্লিক করুন
4. DOCX/PDF হিসেবে ডাউনলোড করতে পারবেন

### ৭. Course File

1. Session-এ **"Course File"** ক্লিক করুন
2. Course File-এর বিভিন্ন components যোগ করুন
3. PDF হিসেবে generate করতে পারবেন

### ৮. Split Course Invitation

**Split Course তৈরি:**
1. Session তৈরি করার সময় **"Course Scope"** select করুন:
   - **Part A** - প্রথম অংশ
   - **Part B** - দ্বিতীয় অংশ
   - **Full** - সম্পূর্ণ কোর্স

**অপর শিক্ষককে Invite:**
1. Session-এ **"Invite Teacher"** ক্লিক করুন
2. শিক্ষক select করুন
3. Part A বা Part B select করুন
4. **"Send Invitation"** ক্লিক করুন

**Invitation Accept/Decline:**
1. **"Invitations"** মেনুতে যান
2. Pending invitations দেখবেন
3. **"Accept"** বা **"Decline"** ক্লিক করুন

---

## কোর্স ম্যানেজমেন্ট

### ১. কারিকুলাম তৈরি

1. **"Curriculum Management"** সেকশনে যান
2. **"Add New Curriculum"** ক্লিক করুন
3. তথ্য দিন:
   - Curriculum Name
   - Date
   - Applicable Batches
4. **"Save"** ক্লিক করুন

### ২. কোর্স যোগ করা

1. Curriculum-এ **"Add Course"** ক্লিক করুন
2. কোর্সের তথ্য দিন:
   - Course Code
   - Course Name
   - Credit
   - Course Type (Theory/Sessional)
   - Nature (Core/Optional)
   - Year & Term
3. **"Save"** ক্লিক করুন

### ৩. শিক্ষক অ্যাসাইন করা

1. **"Assign Teacher"** সেকশনে যান
2. Curriculum, Year, Term, Batch select করুন
3. Course এবং Teacher select করুন
4. **"Assign"** ক্লিক করুন
5. এটি স্বয়ংক্রিয়ভাবে Class Management-এ Session তৈরি করবে

### ৪. স্টুডেন্ট কোর্স রেজিস্ট্রেশন

**স্টুডেন্ট হিসেবে:**
1. **"Course Registration"** মেনুতে যান
2. Academic Session, Year, Term select করুন
3. কোর্সগুলো select করুন
4. **"Save Registration"** ক্লিক করুন
5. **"Send to Coordinator"** ক্লিক করুন (approval-এর জন্য)
6. **"Download Registration PDF"** ক্লিক করুন (PDF ডাউনলোড)

**PDF-এ থাকবে:**
- University Logo
- Student Photo (যদি upload করা থাকে)
- Student Information
- Registered Courses
- Total Credits

**কোঅর্ডিনেটর হিসেবে:**
1. **"Coordinator Registrations"** মেনুতে যান
2. Pending registrations দেখবেন
3. **"Approve"** বা **"Reject"** করতে পারবেন

---

## স্টুডেন্ট ম্যানেজমেন্ট

### ১. নতুন স্টুডেন্ট যোগ করা

1. **"Student Management"** মেনুতে যান
2. **"Add Student"** বাটনে ক্লিক করুন
3. Modal-এ তথ্য দিন:
   - Student ID
   - Name
   - Batch
   - Hall
   - Email
   - Phone Number
4. **"Save Student"** ক্লিক করুন
5. এটি স্বয়ংক্রিয়ভাবে User account তৈরি করবে

### ২. স্টুডেন্ট সম্পাদনা

1. Student list-এ **"Edit"** বাটনে ক্লিক করুন
2. তথ্য আপডেট করুন
3. **"Update Student"** ক্লিক করুন

### ৩. Bulk Upload

1. **"Bulk Upload"** বাটনে ক্লিক করুন
2. Excel file select করুন
3. Column mapping করুন:
   - Student ID
   - Name
   - Batch
   - Hall
   - Email
   - Phone
4. **"Upload"** ক্লিক করুন

---

## রেজাল্ট ম্যানেজমেন্ট

### ১. সেশন তৈরি

1. **"Result Management"** মেনুতে যান
2. **"Add Session"** ক্লিক করুন
3. তথ্য দিন:
   - Session Name
   - Academic Year
   - Batch
   - Year & Term
4. **"Save"** ক্লিক করুন

### ২. সাবজেক্ট যোগ করা

1. Session-এ **"Add Subject"** ক্লিক করুন
2. Subject Code, Name, Credit দিন
3. **"Save"** ক্লিক করুন

### ৩. স্টুডেন্ট যোগ করা

1. Session-এ **"Add Student"** ক্লিক করুন
2. Student ID এবং Name দিন
3. **"Add"** ক্লিক করুন

### ৪. মার্কস ইনপুট

1. **"Add Marks"** সেকশনে যান
2. Subject select করুন
3. প্রতিটি স্টুডেন্টের মার্কস দিন:
   - Theory Marks
   - Sessional Marks (যদি থাকে)
   - Viva Marks (যদি থাকে)
4. **"Save Marks"** ক্লিক করুন

### ৫. রেজাল্ট দেখতে

**Course-wise Result:**
1. **"Course-wise Result"** সেকশনে যান
2. Session এবং Subject select করুন
3. সব স্টুডেন্টের মার্কস দেখবেন

**Student-wise Result:**
1. **"Student-wise Result"** সেকশনে যান
2. Session এবং Student select করুন
3. সব subject-এর মার্কস দেখবেন

### ৬. রেজাল্ট আর্কাইভ

1. **"Archive"** সেকশনে যান
2. পুরানো সেশনগুলো দেখবেন
3. Archive করা সেশন restore করতে পারবেন

---

## রুটিন ম্যানেজমেন্ট

### ১. শিক্ষক যোগ করা

1. **"Routine Management"** মেনুতে যান
2. **"Teachers"** সেকশনে যান
3. **"Add Teacher"** ক্লিক করুন
4. তথ্য দিন:
   - Name
   - Short Name (Callsign)
5. **"Save"** ক্লিক করুন

### ২. রুম যোগ করা

1. **"Rooms"** সেকশনে যান
2. **"Add Room"** ক্লিক করুন
3. Room Name দিন
4. **"Save"** ক্লিক করুন

### ৩. কোর্স যোগ করা

1. **"Courses"** সেকশনে যান
2. **"Add Course"** ক্লিক করুন
3. Course Code এবং Name দিন
4. **"Save"** ক্লিক করুন

### ৪. কোর্স অ্যাসাইন করা

1. **"Assign Course"** সেকশনে যান
2. Course, Teacher, Room, Time select করুন
3. **"Assign"** ক্লিক করুন

### ৫. রুটিন দেখতে

1. **"Routine"** সেকশনে যান
2. Week এবং Day select করুন
3. রুটিন দেখবেন
4. PDF হিসেবে ডাউনলোড করতে পারবেন

---

## প্রোফাইল ম্যানেজমেন্ট

### ১. প্রোফাইল আপডেট

1. Top navigation bar-এ আপনার নামে ক্লিক করুন (বা **"Profile"** মেনুতে যান)
2. **"Update Profile"** পেজে:
   - **Profile Photo** upload করুন (PNG, JPG, JPEG, GIF, WEBP)
   - **Full Name** আপডেট করুন
   - **Email** আপডেট করুন
3. **"Update Profile"** ক্লিক করুন

### ২. পাসওয়ার্ড পরিবর্তন

1. Profile পেজে **"Change Password"** সেকশনে:
   - **Current Password** দিন
   - **New Password** দিন
   - **Confirm New Password** দিন
2. **"Update Profile"** ক্লিক করুন

### ৩. শিক্ষকদের জন্য Call Sign এবং Bank Account No

**শিক্ষক, Dean, বা Head of Discipline** হিসেবে লগইন করলে Profile পেজে অতিরিক্ত সেকশন দেখবেন:

1. **"Teacher Information"** সেকশনে:
   - **Call Sign** - আপনার Call Sign দিন (routine এবং অন্যান্য কাজে ব্যবহৃত হবে)
   - **Bank Account No** - আপনার ব্যাংক একাউন্ট নম্বর দিন (remuneration-এর জন্য)
2. **"Update Profile"** ক্লিক করুন

**নোট:** 
- Photo upload করলে সেটা Course Registration PDF-এ automatically যুক্ত হবে (স্টুডেন্টদের জন্য)
- Call Sign এবং Bank Account No Admin Dashboard-এও দেখা যাবে

---

## সাধারণ সমস্যা সমাধান

### ১. লগইন করতে পারছি না

**সমস্যা:** Username/Password ভুল
- **সমাধান:** 
  - Username/Password double-check করুন
  - "Sign in as" dropdown-এ সঠিক role select করেছেন কিনা দেখুন
  - পাসওয়ার্ড reset করুন

**সমস্যা:** Account নেই
- **সমাধান:** 
  - অ্যাডমিনের সাথে যোগাযোগ করুন
  - শিক্ষক/স্টুডেন্ট account তৈরি করতে হবে

### ২. PDF ডাউনলোড হচ্ছে না

**সমস্যা:** Internal Server Error
- **সমাধান:**
  - Browser console-এ error check করুন
  - File permissions check করুন
  - Server logs check করুন

### ৩. মার্কস save হচ্ছে না

**সমস্যা:** Validation error
- **সমাধান:**
  - মার্কস 0-100 range-এর মধ্যে আছে কিনা check করুন
  - Required fields পূরণ করেছেন কিনা দেখুন
  - Browser refresh করুন

### ৪. Photo upload হচ্ছে না

**সমস্যা:** File size বেশি
- **সমাধান:**
  - Max file size: 16MB
  - Image compress করুন
  - File format check করুন (PNG, JPG, JPEG, GIF, WEBP)

**সমস্যা:** Invalid file type
- **সমাধান:**
  - শুধুমাত্র image files upload করতে পারবেন
  - File extension check করুন

### ৫. Split Course-এ মার্কস দেখাচ্ছে না

**সমস্যা:** অপর শিক্ষক মার্কস দেননি
- **সমাধান:**
  - Part A/B শিক্ষককে remind করুন
  - Invitation accept করেছেন কিনা check করুন

### ৬. Course Registration PDF-এ photo নেই

**সমস্যা:** Photo upload করা নেই
- **সমাধান:**
  - Profile পেজে গিয়ে photo upload করুন
  - Photo upload করার পর PDF generate করুন

---

## গুরুত্বপূর্ণ টিপস

### ✅ Best Practices

1. **Regular Backup:** গুরুত্বপূর্ণ data-এর backup রাখুন
2. **Password Security:** Strong password ব্যবহার করুন
3. **Data Entry:** তথ্য enter করার সময় double-check করুন
4. **Session Management:** Session delete করার আগে backup নিন
5. **Photo Upload:** Course Registration PDF-এর জন্য photo upload করুন

### ⚠️ সতর্কতা

1. **Admin Access:** Admin account শুধুমাত্র authorized person ব্যবহার করবেন
2. **Data Deletion:** Delete করার আগে confirmation নিন
3. **Bulk Upload:** Excel file format check করুন
4. **PDF Generation:** Large data-এর জন্য সময় লাগতে পারে

---

## সহায়তা

### যোগাযোগ

যদি কোনো সমস্যা হয় বা সাহায্যের প্রয়োজন হয়:

1. **System Admin**-এর সাথে যোগাযোগ করুন
2. **Error Logs** check করুন
3. **Browser Console** check করুন (F12 press করুন)

### System Information

- **Version:** 2.0.0
- **Framework:** Flask (Python)
- **Database:** SQLite/MySQL
- **Browser Support:** Chrome, Firefox, Safari, Edge (Latest versions)

---

## Appendix: Keyboard Shortcuts

- **F12:** Browser Developer Tools
- **Ctrl/Cmd + R:** Page Refresh
- **Ctrl/Cmd + S:** Save (form-এ)
- **Esc:** Modal Close

---

**© 2025 Academic Management System - All Rights Reserved**

*এই ম্যানুয়ালটি নিয়মিত আপডেট করা হয়। সর্বশেষ version-এর জন্য GitHub repository check করুন।*

