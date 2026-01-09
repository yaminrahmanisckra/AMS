# সার্ভারে Route Check করার নির্দেশনা

## Step 1: সার্ভারে Route আছে কিনা Check করুন

cPanel Terminal এ এই command run করুন:

```bash
cd /home/gronthon/kulawams.xyz
grep -n "admin/active-semester" app.py
```

**Expected Output:**
```
2019:@app.route('/admin/active-semester')
2072:@app.route('/admin/active-semester/set', methods=['POST'])
2110:@app.route('/admin/active-semester/list', methods=['GET'])
```

**যদি কিছু না দেখায়:**
- সার্ভারে `app.py` file টা সঠিক নয়
- `app.py` file manually upload করতে হবে

## Step 2: Application Load Test করুন

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
python -c "from app import create_app; app = create_app(); print('✅ App loaded successfully')"
```

**যদি Error দেখায়:**
- Error message copy করে share করুন

## Step 3: Application Restart করুন

```bash
cd /home/gronthon/kulawams.xyz
touch passenger_wsgi.py
# 10-15 seconds অপেক্ষা করুন
```

## Step 4: Test করুন

Browser এ **Admin account দিয়ে login করে** visit করুন:

```
https://kulawams.xyz/admin/active-semester
```

**Note:** এই route `@login_required` আছে, তাই login ছাড়া কাজ করবে না।

