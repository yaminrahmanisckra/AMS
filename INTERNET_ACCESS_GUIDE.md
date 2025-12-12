# ইন্টারনেট থেকে Access করার গাইড

## ⚠️ গুরুত্বপূর্ণ: একই WiFi vs ইন্টারনেট

- **একই WiFi:** Router-এর ভিতরে → Port forwarding লাগে না ✅ (এখন কাজ করছে)
- **ইন্টারনেট:** বাইরে থেকে → Router-এ Port Forwarding লাগে ⚙️

---

## 🚀 দ্রুত সমাধান: ngrok (সবচেয়ে সহজ)

**Router config ছাড়াই ২ মিনিটে setup:**

### Step 1: ngrok Install করুন

**macOS:**
```bash
brew install ngrok
```

**অথবা download করুন:**
- https://ngrok.com/download
- Account তৈরি করুন (free)

### Step 2: ngrok Start করুন

**Terminal-এ (app running থাকা অবস্থায়):**
```bash
ngrok http 5001
```

### Step 3: URL ব্যবহার করুন

ngrok একটি URL দেবে, যেমন:
```
https://abc123.ngrok.io
```

**যেকোনো জায়গা থেকে এই URL দিয়ে access করুন!**

**Note:** Free ngrok URLs প্রতিবার restart-এ পরিবর্তন হয়। Fixed URL চাইলে paid plan নিন।

---

## 🔧 Router Port Forwarding (স্থায়ী সমাধান)

### Step 1: Router Admin Panel-এ যান

1. **Router IP খুঁজে বের করুন:**
   ```bash
   # macOS/Linux
   netstat -nr | grep default
   
   # অথবা
   ifconfig | grep "inet " | grep -v 127.0.0.1
   # Gateway IP দেখুন
   ```

   সাধারণত: `192.168.1.1` বা `192.168.0.1`

2. **Browser-এ router IP open করুন:**
   ```
   http://192.168.1.1
   ```

3. **Login করুন:**
   - Username/Password router-এর label-এ আছে
   - অথবা: `admin/admin`, `admin/password`

### Step 2: Port Forwarding Setup করুন

**Router model অনুযায়ী location ভিন্ন হতে পারে:**

#### TP-Link / D-Link:
- **Advanced** → **NAT Forwarding** → **Port Forwarding**
- **Add New** button

#### Netgear:
- **Advanced** → **Port Forwarding / Port Triggering**
- **Add Custom Service**

#### ASUS:
- **WAN** → **Virtual Server / Port Forwarding**
- **Add Profile**

#### Generic Settings:
```
Service Name: Academic Management System
External Port: 5001
Internal IP: 192.168.0.105 (আপনার computer-এর IP)
Internal Port: 5001
Protocol: TCP (বা Both)
Status: Enabled
```

**Save করুন**

### Step 3: Static IP Set করুন (গুরুত্বপূর্ণ!)

**আপনার computer-এর IP static করতে হবে, নাহলে router restart-এ IP পরিবর্তন হবে:**

#### macOS:
1. System Preferences → Network
2. WiFi → Advanced → TCP/IP
3. Configure IPv4: **Manually**
4. IP Address: `192.168.0.105` (আপনার current IP)
5. Subnet Mask: `255.255.255.0`
6. Router: `192.168.0.1` (আপনার router IP)

#### অথবা Router-এ DHCP Reservation:
- Router admin panel → DHCP Settings
- Static IP assignment → আপনার computer-এর MAC address add করুন

### Step 4: Public IP Check করুন

```bash
curl ifconfig.me
```

অথবা visit: https://whatismyipaddress.com/

### Step 5: Test করুন

**বাইরে থেকে (mobile data বা অন্য network):**
```
http://YOUR_PUBLIC_IP:5001
```

**উদাহরণ:**
```
http://123.45.67.89:5001
```

---

## ❌ সাধারণ সমস্যা এবং সমাধান

### সমস্যা 1: "Connection timeout" বা "Can't reach"

**সমাধান:**
1. ✅ Router port forwarding enabled আছে verify করুন
2. ✅ Internal IP সঠিক কিনা check করুন
3. ✅ App running আছে verify করুন (`lsof -i :5001`)
4. ✅ Router firewall rules check করুন

### সমস্যা 2: ISP Port Blocking

**কিছু ISP (বিশেষ করে mobile ISPs) port forwarding block করে:**

**সমাধান:**
- ngrok ব্যবহার করুন (উপরে দেখুন)
- অথবা ISP-কে contact করুন port unblock করতে

### সমস্যা 3: Dynamic Public IP

**আপনার public IP পরিবর্তন হতে পারে:**

**সমাধান:**
- Dynamic DNS (DDNS) service ব্যবহার করুন:
  - No-IP (https://www.noip.com/)
  - DuckDNS (https://www.duckdns.org/)
- Router-এ DDNS configure করুন
- Domain name দিয়ে access করুন: `http://yourname.duckdns.org:5001`

### সমস্যা 4: Port 5001 Blocked

**কিছু ISP port 5001 block করে:**

**সমাধান:**
- ভিন্ন port ব্যবহার করুন (যেমন: 8080, 3000)
- Router-এ external port change করুন
- App-এ: `PORT=8080 ALLOW_NETWORK_ACCESS=1 python3 app.py`

---

## 🔒 নিরাপত্তা সতর্কতা

**ইন্টারনেট থেকে access করার সময়:**

1. ⚠️ **HTTPS ব্যবহার করুন** (SSL certificate)
2. ⚠️ **শক্তিশালী password ব্যবহার করুন**
3. ⚠️ **Firewall rules set করুন** (শুধু trusted IPs allow করুন)
4. ⚠️ **Regular updates করুন**
5. ⚠️ **Access logs monitor করুন**

**Production-এর জন্য:**
- Cloud hosting ব্যবহার করুন (Render, Heroku, AWS)
- Proper web server (Nginx + Gunicorn)
- SSL/HTTPS setup করুন

---

## 📋 Quick Checklist

- [ ] Router admin panel-এ login করতে পারছেন
- [ ] Port forwarding rule add করেছেন
- [ ] Static IP set করেছেন
- [ ] Public IP check করেছেন
- [ ] App running আছে (`ALLOW_NETWORK_ACCESS=1`)
- [ ] Firewall allow করেছেন
- [ ] বাইরে থেকে test করেছেন

---

## 🆘 সহায়তা

**যদি কাজ না করে:**

1. **Test script চালান:**
   ```bash
   ./test_internet_access.sh
   ```

2. **Router logs check করুন**

3. **ISP support-কে contact করুন** (port forwarding support আছে কিনা জানতে)

4. **ngrok ব্যবহার করুন** (temporary solution)

---

## 💡 প্রস্তাবনা

**সবচেয়ে সহজ উপায়: ngrok**

- Setup time: ২ মিনিট
- Router config লাগে না
- SSL automatically (HTTPS)
- Free tier available

**স্থায়ী সমাধান: Cloud Hosting**

- Render.com (free tier)
- Heroku
- AWS
- DigitalOcean
