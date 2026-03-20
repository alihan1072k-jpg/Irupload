<div align="center">

# ☁️ Irupload

**[English](#english) · [فارسی](#فارسی)**

</div>

---

<a name="english"></a>

# ☁️ Irupload — File Share Hub

A lightweight, self-hosted file sharing server built for environments with limited or no internet access.

No frameworks. No package managers. No external dependencies. Just Python.

---

## Why I built this

I needed a dead-simple way to move files on and off a VPS in a restricted network — one where `pip install` and npm don't work reliably, and running Docker is overkill. So I wrote a single-file HTTP server that does exactly what's needed and nothing more.

---

## Features

- **Zero dependencies** — runs on Python 3.8+ standard library only
- **Works fully offline** — no CDN, no external fonts, no analytics
- **Password protected** — session-based auth with brute-force cooldown
- **Drag & drop uploads** — with live progress bar
- **Configurable upload limit** — enforced server-side, not just client-side
- **Dangerous extension blocking** — `.php`, `.sh`, `.exe`, `.py`, etc. are rejected
- **Interactive setup** — one script, done in under a minute
- **Background mode** — survives terminal close via nohup

---

## Requirements

- Python 3.8 or newer (stdlib only — no pip needed)
- Bash
- Linux or macOS

---

## Quick start

```bash
git clone https://github.com/alihan1072k-jpg/Irupload.git
cd Irupload
bash install.sh
```

The setup wizard walks you through five steps:

```
[1/5]  Server Port          (default: 5000)
[2/5]  Display Name         (default: My File Server)
[3/5]  Password             (min 6 chars, confirmed twice)
[4/5]  Run Mode             (foreground or background)
[5/5]  Max Upload Size      (default: 200 MB)
```

That's it. The server starts automatically after setup.

---

## Manual setup

```bash
cp fileserver.conf.example fileserver.conf
nano fileserver.conf
python3 main.py
```

---

## Configuration

All settings live in `fileserver.conf` — created by the installer, never committed to git.

```ini
PORT=5000
SITE_NAME=My File Server
PASSWORD=your_password_here
MAX_UPLOAD_SIZE_MB=200
```

> `fileserver.conf` is in `.gitignore` and will never be pushed to any repository.

---

## Managing the server

```bash
bash manage.sh
# or
upfile
```

The manager lets you change password, port, site name, upload limit, start/stop/restart the server, and check live status.

---

## Security

| Concern | How it's handled |
|---------|-----------------|
| Authentication | Cookie holds SHA-256 hash of password, not the raw value |
| Brute-force | 5 failed logins triggers a 30-second per-IP cooldown |
| Directory traversal | `realpath()` check ensures all paths stay inside `uploads/` |
| Dangerous extensions | Upload blocked for `.php .sh .exe .py .bat .cgi` and more |
| Upload size | Enforced server-side — cannot be bypassed by the client |
| Password in logs | Never printed, even during setup or in error output |
| Config permissions | `fileserver.conf` is written with mode `600` |

### SSL / HTTPS

The server speaks plain HTTP. Put it behind a reverse proxy that handles TLS:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
}
```

---

## Project layout

```
Irupload/
├── main.py                   # the server
├── install.sh                # setup wizard
├── manage.sh                 # server manager
├── fileserver.conf.example   # config template
├── SECURITY_AUDIT.md         # full security review
└── uploads/                  # where files land (auto-created, gitignored)
```

---

## License

MIT

---

<br>

---

<a name="فارسی"></a>

<div dir="rtl">

# ☁️ Irupload — سرور اشتراک‌گذاری فایل

یک سرور سبک و خودمیزبان برای آپلود و دانلود فایل، طراحی‌شده برای محیط‌هایی با دسترسی محدود به اینترنت.

بدون فریمورک. بدون package manager. بدون وابستگی خارجی. فقط Python.

---

## چرا نوشتمش

نیاز داشتم فایل‌ها رو روی یه VPS با شبکه محدود جابجا کنم — جایی که `pip install` و npm درست کار نمی‌کنن و Docker هم سنگینه. یه سرور HTTP تک‌فایلی نوشتم که دقیقاً همین کار رو بکنه و نه بیشتر.

---

## ویژگی‌ها

- **صفر وابستگی** — فقط با کتابخانه استاندارد Python 3.8+ کار می‌کنه
- **کاملاً آفلاین** — بدون CDN، بدون فونت خارجی، بدون analytics
- **محافظت با رمز عبور** — احراز هویت با محافظت در برابر Brute-force
- **آپلود Drag & Drop** — با نوار پیشرفت زنده
- **محدودیت حجم قابل تنظیم** — اعمال‌شده سمت سرور، قابل دور زدن نیست
- **بلاک پسوندهای خطرناک** — `.php`، `.sh`، `.exe`، `.py` و غیره رد می‌شن
- **نصب تعاملی** — یک اسکریپت، زیر یک دقیقه
- **اجرا در پس‌زمینه** — با nohup از بسته شدن ترمینال جان سالم به در می‌بره

---

## پیش‌نیازها

- Python نسخه ۳.۸ یا بالاتر (بدون نیاز به pip)
- Bash
- Linux یا macOS

---

## نصب سریع

</div>

```bash
git clone https://github.com/alihan1072k-jpg/Irupload.git
cd Irupload
bash install.sh
```

<div dir="rtl">

اسکریپت نصب پنج سوال می‌پرسد:

```
[1/5]  پورت سرور          (پیش‌فرض: 5000)
[2/5]  نام نمایشی         (پیش‌فرض: My File Server)
[3/5]  رمز عبور            (حداقل ۶ کاراکتر، تأیید دوباره)
[4/5]  حالت اجرا           (foreground یا background)
[5/5]  حداکثر حجم آپلود   (پیش‌فرض: 200 مگابایت)
```

بعد از نصب، سرور به‌صورت خودکار شروع به کار می‌کند.

---

## نصب دستی

</div>

```bash
cp fileserver.conf.example fileserver.conf
nano fileserver.conf
python3 main.py
```

<div dir="rtl">

---

## تنظیمات

همه تنظیمات در فایل `fileserver.conf` قرار دارند — توسط installer ساخته می‌شه و هرگز به گیت‌هاب push نمی‌شه.

</div>

```ini
PORT=5000
SITE_NAME=My File Server
PASSWORD=your_password_here
MAX_UPLOAD_SIZE_MB=200
```

<div dir="rtl">

> فایل `fileserver.conf` در `.gitignore` قرار دارد و هرگز commit نمی‌شود.

---

## مدیریت سرور

</div>

```bash
bash manage.sh
# یا
upfile
```

<div dir="rtl">

از طریق منوی مدیریت می‌توانید رمز عبور، پورت، نام سایت و حجم آپلود را تغییر دهید، سرور را شروع/متوقف/ریستارت کنید و وضعیت زنده را ببینید.

---

## امنیت

| موضوع | روش |
|-------|-----|
| احراز هویت | Cookie حاوی هش SHA-256 رمز عبور است، نه خود رمز |
| Brute-force | ۵ تلاش ناموفق = قفل ۳۰ ثانیه‌ای per-IP |
| Directory Traversal | بررسی `realpath()` برای همه مسیرها |
| پسوندهای خطرناک | بلاک `.php .sh .exe .py .bat .cgi` و بیشتر |
| حجم آپلود | اعمال سمت سرور — قابل دور زدن نیست |
| رمز عبور در لاگ | هرگز چاپ نمی‌شود |
| مجوز فایل کانفیگ | `fileserver.conf` با دسترسی `600` نوشته می‌شود |

### SSL / HTTPS

سرور روی HTTP ساده کار می‌کند. SSL باید توسط reverse proxy مدیریت شود (Nginx، Caddy، Parspack).

---

## ساختار پروژه

```
Irupload/
├── main.py                   # سرور اصلی
├── install.sh                # اسکریپت نصب
├── manage.sh                 # مدیریت سرور
├── fileserver.conf.example   # نمونه تنظیمات
├── SECURITY_AUDIT.md         # گزارش امنیتی
└── uploads/                  # فایل‌های آپلودشده (gitignored)
```

---

## لایسنس

MIT

</div>
