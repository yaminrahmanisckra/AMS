# 🚀 Academic Management System - Startup Guide

## সহজ উপায় (সবচেয়ে ভালো)

```bash
./run_app.sh
```

## অন্যান্য উপায়

### 1. Network Access সহ (প্রস্তাবিত)
```bash
ALLOW_NETWORK_ACCESS=1 python3 app.py
```

### 2. Virtual Environment সহ
```bash
ALLOW_NETWORK_ACCESS=1 .venv/bin/python app.py
```

### 3. Custom Port দিয়ে
```bash
PORT=5002 ALLOW_NETWORK_ACCESS=1 python3 app.py
```

### 4. শুধু Localhost
```bash
python3 app.py
```

## এপ এক্সেস করুন

**Local Access:**
- http://127.0.0.1:5001

**Network Access (অন্য ডিভাইস থেকে):**
- http://YOUR_IP:5001
- (IP ঠিকানা startup message-এ দেখাবে)

## সার্ভার বন্ধ করতে

`CTRL + C` চাপুন

অথবা terminal-এ:
```bash
pkill -f "python3 app.py"
```

## Troubleshooting

### Port already in use?
```bash
# Port 5001 খালি করুন
lsof -ti:5001 | xargs kill -9

# তারপর আবার চালু করুন
./run_app.sh
```

### WeasyPrint Error?
```bash
# run_app.sh ব্যবহার করুন (এটি automatically fix করে)
./run_app.sh
```

## Default Settings

- **Port**: 5001
- **Host**: 0.0.0.0 (network access) বা 127.0.0.1 (localhost only)
- **Database**: SQLite (instance/academic_management.db)
