# Academic Management System - পোর্ট ফরওয়ার্ডিং গাইড

## ⚡ দ্রুত শুরু (Quick Start)

### ⚠️ গুরুত্বপূর্ণ: Firewall Allow করুন (macOS)

**macOS Firewall blocking করছে কিনা check করুন:**
```bash
./fix_firewall.sh
```

**অথবা manually:**
1. System Preferences → Security & Privacy → Firewall
2. Firewall Options → "+" button
3. Python-কে add করুন এবং "Allow incoming connections" set করুন

### App Start করুন

**সহজ উপায় - Script ব্যবহার করুন:**
```bash
./start_network.sh
```

এই script automatically:
- Port check করবে
- IP address দেখাবে
- Network access enable করে app start করবে

**Manual Start:**
```bash
ALLOW_NETWORK_ACCESS=1 python3 app.py
```

---

## নেটওয়ার্ক এক্সেস সেটআপ

### অপশন ১: লোকাল নেটওয়ার্ক এক্সেস (একই WiFi/LAN)

#### ধাপ ১: নেটওয়ার্ক এক্সেস সক্রিয় করুন
App চালানোর আগে environment variable সেট করুন:

**macOS/Linux:**
```bash
export ALLOW_NETWORK_ACCESS=1
python3 app.py
```

**Windows:**
```cmd
set ALLOW_NETWORK_ACCESS=1
python app.py
```

অথবা সরাসরি:
```bash
ALLOW_NETWORK_ACCESS=1 python3 app.py
```

#### ধাপ ২: আপনার লোকাল IP ঠিকানা খুঁজে বের করুন

**macOS:**
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

**Windows:**
```cmd
ipconfig
```
আপনার active network adapter-এর নিচে "IPv4 Address" দেখুন।

**Linux:**
```bash
hostname -I
```

#### ধাপ ৩: অন্যান্য ডিভাইস থেকে এক্সেস করুন
- নিশ্চিত করুন আপনার device একই WiFi/LAN network-এ আছে
- অন্য device-এ browser খুলুন
- যান: `http://YOUR_LOCAL_IP:5001`
- উদাহরণ: `http://192.168.0.105:5001`

---

### অপশন ২: এক্সটার্নাল এক্সেস (ইন্টারনেট থেকে Access)

**📖 বিস্তারিত গাইড:** `INTERNET_ACCESS_GUIDE.md` file দেখুন

**⚡ দ্রুত সমাধান (ngrok - সবচেয়ে সহজ):**
```bash
# ngrok install করুন
brew install ngrok

# App running থাকা অবস্থায়
ngrok http 5001
```

**🔧 Router Port Forwarding (স্থায়ী সমাধান):**

#### ধাপ ১: নেটওয়ার্ক এক্সেস সক্রিয় করুন
অপশন ১-এর মতো - `ALLOW_NETWORK_ACCESS=1` সেট করুন

#### ধাপ ২: Router-এ পোর্ট ফরওয়ার্ডিং কনফিগার করুন

1. **আপনার Router-এর IP খুঁজে বের করুন:**
   - সাধারণত `192.168.1.1` বা `192.168.0.1`
   - Router label বা network settings-এ দেখুন

2. **Router Admin Panel-এ প্রবেশ করুন:**
   - Browser খুলুন: `http://192.168.1.1` (বা আপনার router IP)
   - Admin credentials দিয়ে login করুন

3. **পোর্ট ফরওয়ার্ডিং সেটআপ করুন:**
   - "Port Forwarding" বা "Virtual Server" section-এ যান
   - নতুন rule যোগ করুন:
     - **Service Name:** Academic Management System
     - **External Port:** 5001 (বা আপনার পছন্দের port)
     - **Internal IP:** আপনার computer-এর local IP (যেমন: 192.168.0.105)
     - **Internal Port:** 5001
     - **Protocol:** TCP
     - **Status:** Enabled

4. **Save এবং Apply করুন**

#### ধাপ ৩: আপনার Public IP খুঁজে বের করুন

**আপনার public IP check করুন:**
```bash
curl ifconfig.me
```
অথবা visit করুন: https://whatismyipaddress.com/

#### ধাপ ৪: বাইরে থেকে এক্সেস করুন
- Internet আছে এমন যেকোনো device থেকে:
- যান: `http://YOUR_PUBLIC_IP:5001`
- উদাহরণ: `http://123.45.67.89:5001`

---

### অপশন ৩: ngrok ব্যবহার (Temporary Tunnel - Router Config ছাড়াই)

1. **ngrok install করুন:**
   ```bash
   # macOS
   brew install ngrok
   
   # অথবা https://ngrok.com/ থেকে download করুন
   ```

2. **আপনার app start করুন:**
   ```bash
   python3 app.py
   ```

3. **Tunnel তৈরি করুন:**
   ```bash
   ngrok http 5001
   ```

4. **প্রদত্ত URL ব্যবহার করুন:**
   - ngrok একটি URL দেবে যেমন: `https://abc123.ngrok.io`
   - যেকোনো জায়গা থেকে access করতে এই URL share করুন
   - **Note:** Free ngrok URLs প্রতিবার restart-এ পরিবর্তন হয়

---

## নিরাপত্তা বিবেচনা

### লোকাল নেটওয়ার্ক এক্সেসের জন্য:
- ✅ Home/office network-এর জন্য নিরাপদ
- ✅ শুধুমাত্র আপনার network-এর ভিতরে accessible
- ⚠️ নিশ্চিত করুন আপনার WiFi password protected

### এক্সটার্নাল এক্সেসের জন্য (পোর্ট ফরওয়ার্ডিং):
- ⚠️ **নিরাপত্তা ঝুঁকি:** আপনার app internet থেকে accessible হবে
- ✅ **প্রস্তাবিত নিরাপত্তা ব্যবস্থা:**
  1. HTTPS (SSL certificate) ব্যবহার করুন
  2. শক্তিশালী authentication implement করুন
  3. Firewall rules ব্যবহার করুন
  4. পরিবর্তে VPN ব্যবহার করার কথা বিবেচনা করুন
  5. Application নিয়মিত update করুন
  6. Access logs monitor করুন

### Production-এর জন্য:
- Proper web server ব্যবহার করুন (Nginx, Apache)
- WSGI server ব্যবহার করুন (Gunicorn, uWSGI)
- SSL/HTTPS setup করুন
- Sensitive data-এর জন্য environment variables ব্যবহার করুন
- Rate limiting implement করুন
- Reverse proxy ব্যবহার করুন

---

## Firewall কনফিগারেশন

### macOS Firewall:
1. System Preferences → Security & Privacy → Firewall
2. "Firewall Options" click করুন
3. Python-কে allowed applications-এ যোগ করুন
4. অথবা port 5001-এ incoming connections allow করুন

### Windows Firewall:
1. Windows Security → Firewall & network protection
2. Advanced settings
3. Inbound Rules → New Rule
4. Port → TCP → 5001 → Allow connection

### Linux (UFW):
```bash
sudo ufw allow 5001/tcp
sudo ufw reload
```

---

## সমস্যা সমাধান

### অন্যান্য devices থেকে access করতে পারছেন না:
1. ✅ Check করুন `ALLOW_NETWORK_ACCESS=1` set করা আছে কিনা
2. ✅ Verify করুন দুটি device একই network-এ আছে
3. ✅ Firewall settings check করুন
4. ✅ IP address সঠিক কিনা verify করুন
5. ✅ Test করার জন্য temporarily firewall disable করে দেখুন

### পোর্ট ফরওয়ার্ডিং কাজ করছে না:
1. ✅ Verify করুন router port forwarding enabled আছে
2. ✅ Check করুন আপনার ISP port forwarding block করে কিনা
3. ✅ Verify করুন internal IP পরিবর্তন হয়নি (static IP ব্যবহার করুন)
4. ✅ Router logs check করুন
5. ✅ ভিন্ন external port try করুন

### Connection refused:
1. ✅ নিশ্চিত করুন app running আছে
2. ✅ Check করুন port 5001 available আছে কিনা
3. ✅ Verify করুন host 0.0.0.0-এ set করা আছে
4. ✅ Check করুন অন্য applications port 5001 ব্যবহার করছে কিনা

---

## দ্রুত শুরু করার Commands

**লোকাল নেটওয়ার্ক এক্সেস:**
```bash
ALLOW_NETWORK_ACCESS=1 python3 app.py
```

**লোকাল IP check করুন:**
```bash
# macOS
ifconfig | grep "inet " | grep -v 127.0.0.1

# Linux
hostname -I

# Windows
ipconfig
```

**Connection test করুন:**
```bash
# একই network-এর অন্য device থেকে
curl http://YOUR_LOCAL_IP:5001
```

---

## গুরুত্বপূর্ণ নোট

- Default port হল **5001**
- `PORT` environment variable set করে port পরিবর্তন করুন
- Production-এর জন্য proper deployment ব্যবহার করুন (পোর্ট ফরওয়ার্ডিং নয়)
- Better security-এর জন্য cloud hosting বিবেচনা করুন (Render, Heroku, AWS)

---

## ব্যবহারের উদাহরণ

### উদাহরণ ১: একই WiFi-তে Mobile থেকে Access

1. **Computer-এ app চালান:**
   ```bash
   ALLOW_NETWORK_ACCESS=1 python3 app.py
   ```

2. **Console-এ দেখবেন:**
   ```
   Server running on ALL network interfaces
   Local access: http://127.0.0.1:5001
   Network access: http://192.168.0.105:5001
   ```

3. **Mobile phone-এ browser খুলুন:**
   - একই WiFi network-এ connect করুন
   - Browser-এ যান: `http://192.168.0.105:5001`
   - Login করুন এবং ব্যবহার করুন

### উদাহরণ ২: Router Port Forwarding

1. **Router admin panel-এ যান:** `http://192.168.1.1`

2. **Port Forwarding section-এ:**
   - External Port: `5001`
   - Internal IP: `192.168.0.105` (আপনার computer-এর IP)
   - Internal Port: `5001`
   - Protocol: `TCP`

3. **Save করুন**

4. **Public IP check করুন:**
   ```bash
   curl ifconfig.me
   ```

5. **যেকোনো জায়গা থেকে access করুন:**
   - Browser-এ যান: `http://YOUR_PUBLIC_IP:5001`

---

## সহায়তা

যদি কোনো সমস্যা হয়:
1. Console-এ error messages check করুন
2. Firewall settings verify করুন
3. Network connection test করুন
4. Router logs check করুন
5. Port availability verify করুন

---

## সমস্যা সমাধান: একই WiFi থেকে Access করতে পারছেন না

### ধাপ ১: Network Test Script চালান
```bash
./test_network_access.sh
```

এই script আপনাকে বলবে:
- আপনার local IP address
- App running আছে কিনা
- Localhost access কাজ করছে কিনা
- Network access কাজ করছে কিনা
- Firewall status

### ধাপ ২: সাধারণ সমস্যা এবং সমাধান

#### সমস্যা: "Connection refused" বা "Can't reach this page"
**সমাধান:**
1. ✅ নিশ্চিত করুন app running আছে:
   ```bash
   ALLOW_NETWORK_ACCESS=1 python3 app.py
   ```

2. ✅ Console-এ দেখুন:
   ```
   Server running on ALL network interfaces
   Network access: http://192.168.0.105:5001
   ```

3. ✅ macOS Firewall check করুন:
   - System Preferences → Security & Privacy → Firewall
   - Firewall Options → Python-কে allow করুন
   - অথবা temporarily firewall disable করে test করুন

4. ✅ IP address verify করুন:
   ```bash
   ifconfig | grep "inet " | grep -v 127.0.0.1
   ```

#### সমস্যা: Socket errors দেখাচ্ছে (OSError: Socket is not connected)
**সমাধান:**
- এগুলো harmless errors - client দ্রুত disconnect করলে হয়
- App কাজ করছে কিনা check করুন browser-এ
- যদি app কাজ করে, এই errors ignore করতে পারেন

#### সমস্যা: Mobile/Tablet থেকে access করতে পারছেন না
**সমাধান:**
1. ✅ নিশ্চিত করুন mobile device একই WiFi network-এ আছে
2. ✅ Computer-এর exact IP address ব্যবহার করুন
3. ✅ Browser-এ URL: `http://192.168.0.105:5001` (আপনার IP)
4. ✅ `http://` prefix নিশ্চিত করুন (https নয়)
5. ✅ Port number (`:5001`) include করুন

#### সমস্যা: Internet থেকে access করতে পারছেন না
**সমাধান:**
1. ✅ Router-এ port forwarding setup করুন (guide-এর Option 2 দেখুন)
2. ✅ Public IP check করুন: `curl ifconfig.me`
3. ✅ ISP port blocking check করুন (কিছু ISP port forwarding block করে)
4. ✅ Router admin panel-এ port forwarding verify করুন

### ধাপ ৩: Manual Testing

**Computer-এ test করুন:**
```bash
# Terminal-এ test করুন
curl http://127.0.0.1:5001

# Browser-এ test করুন
open http://127.0.0.1:5001
```

**Network-এ test করুন (একই computer থেকে):**
```bash
# আপনার local IP দিয়ে test করুন
curl http://192.168.0.105:5001
```

**Mobile device থেকে test করুন:**
1. Mobile-এ browser খুলুন
2. URL bar-এ type করুন: `http://192.168.0.105:5001`
3. Enter press করুন

### ধাপ ৪: Firewall Allow করুন (macOS)

**Option 1: System Preferences**
1. System Preferences → Security & Privacy → Firewall
2. Click "Firewall Options"
3. "+" button click করুন
4. Applications → Python → Add করুন
5. "Allow incoming connections" select করুন

**Option 2: Command Line (Temporary)**
```bash
# Port 5001 allow করুন
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/bin/python3
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp /usr/bin/python3
```

### ধাপ ৫: Port Change করুন (যদি 5001 কাজ না করে)

```bash
# Port 8080 ব্যবহার করুন
PORT=8080 ALLOW_NETWORK_ACCESS=1 python3 app.py
```

তারপর access করুন: `http://YOUR_IP:8080`

---

## Quick Diagnostic Commands

```bash
# 1. IP address check
ifconfig | grep "inet " | grep -v 127.0.0.1

# 2. Port check (app running আছে কিনা)
lsof -i :5001

# 3. Localhost test
curl http://127.0.0.1:5001

# 4. Network test (আপনার IP দিয়ে)
curl http://192.168.0.105:5001

# 5. Firewall status (macOS)
/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
```

---

## গুরুত্বপূর্ণ Tips

1. **সবসময় `ALLOW_NETWORK_ACCESS=1` set করুন network access-এর জন্য**
2. **Console-এ দেখানো IP address use করুন**
3. **Browser-এ `http://` prefix নিশ্চিত করুন (https নয়)**
4. **Port number (`:5001`) include করুন**
5. **Firewall temporarily disable করে test করুন**
6. **দুটি device একই WiFi network-এ আছে verify করুন**
