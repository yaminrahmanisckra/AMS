# cPanel: কাস্টম এন্ট্রি সেভ – ম্যানুয়ালি ডাটাবেস আপডেট

লোকালে কাস্টম এন্ট্রি সেভ থাকলেও cPanel-এ না থাকলে `routine` টেবিলে দুটো কলাম ম্যানুয়ালি যোগ করুন।

## ম্যানুয়াল স্টেপ (phpMyAdmin)

1. cPanel থেকে **phpMyAdmin** খুলুন।
2. বাম পাশ থেকে আপনার অ্যাপের **ডাটাবেস** সিলেক্ট করুন।
3. উপরে **SQL** ট্যাবে ক্লিক করুন।
4. নিচের **প্রথম লাইন** কপি করে SQL বক্সে পেস্ট করুন, তারপর **Go** চাপুন।

   ```sql
   ALTER TABLE routine ADD COLUMN is_custom TINYINT(1) DEFAULT 0;
   ```

5. যদি "Duplicate column name 'is_custom'" আসে, মানে কলাম আগে থেকেই আছে — সেক্ষেত্রে কিছু করবেন না।  
   যদি সফল হয়, পরের ধাপে যান।
6. এবার **দ্বিতীয় লাইন** কপি করে আবার SQL বক্সে পেস্ট করে **Go** চাপুন।

   ```sql
   ALTER TABLE routine ADD COLUMN custom_course_name VARCHAR(200) NULL;
   ```

7. "Duplicate column name 'custom_course_name'" এলে সেটাও আগে থেকে আছে।  
   দুটোই একবার চালিয়ে দেখলেই হবে।

এরপর সাইটে গিয়ে আবার কাস্টম এন্ট্রি দিয়ে সেভ করে চেক করুন।

---

**একই কাজ ফাইলে:** প্রজেক্টে `migrations/add_routine_custom_columns_standalone.sql` ফাইল আছে; ওখান থেকে দুটো লাইন কপি করে phpMyAdmin-এ এক এক করে চালাতে পারেন।
