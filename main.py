import http.server
import socketserver
import os
import urllib.parse
import html
import datetime
import shutil
import hashlib
import time
import threading

# --- بارگذاری تنظیمات از فایل کانفیگ ---
CONFIG_FILE = "fileserver.conf"

def load_config():
    """
    Load configuration from fileserver.conf.
    Exits immediately if the file is missing or PASSWORD is not set.
    No hardcoded passwords exist anywhere in this file.
    """
    if not os.path.exists(CONFIG_FILE):
        print("=" * 60)
        print("ERROR: fileserver.conf not found.")
        print("Run 'bash install.sh' to set up the server,")
        print("or copy fileserver.conf.example to fileserver.conf")
        print("and set a strong PASSWORD before starting.")
        print("=" * 60)
        raise SystemExit(1)

    config = {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                config[key.strip()] = val.strip()

    if not config.get("PASSWORD"):
        print("=" * 60)
        print("ERROR: PASSWORD is not set in fileserver.conf.")
        print("Please set a strong password and restart.")
        print("=" * 60)
        raise SystemExit(1)

    return config

cfg = load_config()
PORT = int(os.environ.get("PORT", cfg.get("PORT", "5000")))
PASSWORD = cfg["PASSWORD"]
SITE_NAME = cfg.get("SITE_NAME", "File Share Hub")

# Parse MAX_UPLOAD_SIZE_MB with safe fallback
try:
    MAX_UPLOAD_SIZE_MB = int(cfg.get("MAX_UPLOAD_SIZE_MB", "200"))
    if MAX_UPLOAD_SIZE_MB < 1:
        MAX_UPLOAD_SIZE_MB = 200
except ValueError:
    MAX_UPLOAD_SIZE_MB = 200

MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Dangerous extensions that cannot be uploaded ---
BLOCKED_EXTENSIONS = {
    ".php", ".php3", ".php4", ".php5", ".php7", ".phtml",
    ".sh", ".bash", ".zsh",
    ".exe", ".bat", ".cmd", ".com",
    ".cgi", ".pl", ".rb",
    ".py",                    # scripts; use rename if you need Python notebooks
    ".htaccess", ".htpasswd",
    ".jsp", ".jspx", ".asp", ".aspx",
    ".cfm",
}

# --- Auth token: SHA-256 of the password (not the raw password) ---
# This means the cookie contains a hash, not the literal password.
AUTH_TOKEN = hashlib.sha256(PASSWORD.encode()).hexdigest()

# --- Brute-force protection ---
# { ip_address: {"failures": int, "locked_until": float} }
_login_attempts: dict = {}
_login_lock = threading.Lock()
MAX_LOGIN_FAILURES = 5
LOCKOUT_SECONDS = 30


def _check_lockout(ip: str) -> bool:
    """Return True if the IP is currently locked out."""
    with _login_lock:
        entry = _login_attempts.get(ip)
        if not entry:
            return False
        if entry["failures"] >= MAX_LOGIN_FAILURES:
            if time.time() < entry["locked_until"]:
                return True
            # Lockout expired — reset
            _login_attempts.pop(ip, None)
    return False


def _record_failure(ip: str):
    with _login_lock:
        entry = _login_attempts.setdefault(ip, {"failures": 0, "locked_until": 0.0})
        entry["failures"] += 1
        if entry["failures"] >= MAX_LOGIN_FAILURES:
            entry["locked_until"] = time.time() + LOCKOUT_SECONDS


def _record_success(ip: str):
    with _login_lock:
        _login_attempts.pop(ip, None)


def _safe_filename(raw: str) -> str | None:
    """
    Validate and sanitise an upload filename.
    Returns the cleaned filename, or None if the filename is rejected.
    """
    # Reject null bytes and control characters
    if "\x00" in raw or any(ord(c) < 32 for c in raw):
        return None

    # Strip path components
    name = os.path.basename(raw)

    # Reject empty names and dot-only names
    if not name or name in (".", ".."):
        return None

    # Reject blocked extensions
    ext = os.path.splitext(name)[1].lower()
    if ext in BLOCKED_EXTENSIONS:
        return None

    # Reject filenames that are too long (filesystem safety)
    if len(name.encode("utf-8")) > 240:
        return None

    return name


def _safe_filepath(filename: str) -> str | None:
    """
    Return the absolute path for a file inside UPLOAD_DIR,
    or None if the resolved path escapes the upload directory.
    """
    real_upload_dir = os.path.realpath(UPLOAD_DIR)
    candidate = os.path.realpath(os.path.join(UPLOAD_DIR, filename))
    if not candidate.startswith(real_upload_dir + os.sep) and candidate != real_upload_dir:
        return None
    return candidate


def file_icon(filename):
    """بازگرداندن آیکون اموجی بر اساس پسوند فایل"""
    ext = os.path.splitext(filename)[1].lower()
    icons = {
        ".pdf": "📄", ".doc": "📝", ".docx": "📝", ".txt": "📃",
        ".xls": "📊", ".xlsx": "📊", ".csv": "📊",
        ".ppt": "📑", ".pptx": "📑",
        ".zip": "🗜️", ".rar": "🗜️", ".tar": "🗜️", ".gz": "🗜️", ".7z": "🗜️",
        ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️",
        ".svg": "🖼️", ".webp": "🖼️", ".bmp": "🖼️",
        ".mp4": "🎬", ".mkv": "🎬", ".avi": "🎬", ".mov": "🎬", ".webm": "🎬",
        ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵", ".ogg": "🎵",
        ".js": "📜", ".ts": "📜", ".html": "🌐", ".css": "🎨",
        ".json": "📋", ".xml": "📋",
        ".iso": "💿", ".dmg": "💿",
    }
    return icons.get(ext, "📁")


def format_size(size_bytes):
    """فرمت‌بندی حجم فایل"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    else:
        return f"{size_bytes/(1024*1024):.2f} MB"


CSS = """
  :root {
    --primary: #6c63ff;
    --primary-dark: #574fd6;
    --primary-light: #ede9ff;
    --danger: #ff5c7a;
    --danger-dark: #e0445f;
    --success: #22c55e;
    --success-dark: #16a34a;
    --bg: #f0f2ff;
    --surface: #ffffff;
    --surface2: #f8f8ff;
    --text: #1e1b4b;
    --text-muted: #7c7aa3;
    --border: #e2e0f4;
    --radius: 18px;
    --radius-sm: 10px;
    --shadow: 0 4px 24px rgba(108,99,255,0.10);
    --shadow-lg: 0 8px 40px rgba(108,99,255,0.16);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: Tahoma, 'Segoe UI', Arial, sans-serif;
    background: var(--bg);
    min-height: 100vh;
    color: var(--text);
    padding: 24px 16px;
    direction: rtl;
  }
  .container {
    max-width: 760px;
    margin: 0 auto;
  }
  /* ---- هدر ---- */
  .topbar {
    background: linear-gradient(135deg, var(--primary) 0%, #a084ee 100%);
    border-radius: var(--radius);
    padding: 22px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
    box-shadow: var(--shadow-lg);
  }
  .topbar-title {
    display: flex;
    align-items: center;
    gap: 12px;
    color: #fff;
  }
  .topbar-title .logo { font-size: 28px; }
  .topbar-title h1 { font-size: 20px; font-weight: bold; }
  .topbar-title p { font-size: 13px; opacity: .8; margin-top: 2px; }
  .logout-btn {
    background: rgba(255,255,255,0.18);
    color: #fff;
    border: 1.5px solid rgba(255,255,255,0.35);
    border-radius: var(--radius-sm);
    padding: 8px 18px;
    font-size: 14px;
    cursor: pointer;
    text-decoration: none;
    transition: background 0.2s;
    font-family: inherit;
  }
  .logout-btn:hover { background: rgba(255,255,255,0.30); }

  /* ---- کارت آپلود ---- */
  .card {
    background: var(--surface);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 28px;
    margin-bottom: 24px;
    border: 1.5px solid var(--border);
  }
  .card-title {
    font-size: 16px;
    font-weight: bold;
    color: var(--text);
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  /* ---- ناحیه drag & drop ---- */
  .drop-zone {
    border: 2px dashed var(--primary);
    border-radius: var(--radius-sm);
    background: var(--primary-light);
    padding: 32px 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: 18px;
    position: relative;
  }
  .drop-zone.dragover { background: #d8d2ff; border-color: var(--primary-dark); }
  .drop-zone-icon { font-size: 38px; margin-bottom: 10px; }
  .drop-zone-text { color: var(--text-muted); font-size: 14px; }
  .drop-zone-text span { color: var(--primary); font-weight: bold; cursor: pointer; }
  .drop-zone input[type=file] {
    position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
  }
  .selected-file {
    display: none;
    background: var(--surface2);
    border: 1.5px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 10px 16px;
    font-size: 14px;
    margin-bottom: 14px;
    align-items: center;
    gap: 10px;
  }
  .selected-file.show { display: flex; }
  .selected-file .sf-name { flex: 1; word-break: break-all; font-weight: bold; }
  .selected-file .sf-size { color: var(--text-muted); font-size: 12px; }

  /* ---- دکمه آپلود ---- */
  .upload-btn {
    width: 100%;
    padding: 13px;
    background: linear-gradient(90deg, var(--primary) 0%, #a084ee 100%);
    color: #fff;
    border: none;
    border-radius: var(--radius-sm);
    font-size: 16px;
    font-family: inherit;
    cursor: pointer;
    font-weight: bold;
    transition: opacity 0.2s, transform 0.1s;
    box-shadow: 0 4px 16px rgba(108,99,255,0.25);
  }
  .upload-btn:hover { opacity: 0.92; transform: translateY(-1px); }
  .upload-btn:active { transform: translateY(0); }
  .upload-btn:disabled { opacity: 0.55; cursor: not-allowed; transform: none; }

  /* ---- نوار پیشرفت ---- */
  .progress-wrap { display: none; margin-top: 18px; }
  .progress-track {
    width: 100%;
    height: 10px;
    background: var(--border);
    border-radius: 99px;
    overflow: hidden;
    margin-bottom: 8px;
  }
  .progress-fill {
    height: 100%;
    width: 0%;
    background: linear-gradient(90deg, var(--primary) 0%, var(--success) 100%);
    border-radius: 99px;
    transition: width 0.25s ease;
  }
  .progress-info {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    color: var(--text-muted);
    direction: ltr;
  }

  /* ---- لیست فایل‌ها ---- */
  .files-count {
    background: var(--primary);
    color: #fff;
    border-radius: 99px;
    font-size: 12px;
    padding: 2px 10px;
    font-weight: bold;
  }
  .empty-state {
    text-align: center;
    padding: 40px 0;
    color: var(--text-muted);
  }
  .empty-state .empty-icon { font-size: 48px; margin-bottom: 12px; }
  .empty-state p { font-size: 15px; }

  .file-item {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--surface2);
    border: 1.5px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 14px 16px;
    margin-bottom: 12px;
    transition: box-shadow 0.2s, transform 0.15s;
  }
  .file-item:hover { box-shadow: var(--shadow); transform: translateY(-1px); }
  .file-icon { font-size: 26px; flex-shrink: 0; }
  .file-info {
    flex: 1;
    min-width: 0;
  }
  .file-name {
    font-size: 15px;
    font-weight: bold;
    color: var(--text);
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }
  .file-meta {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
    display: flex;
    gap: 10px;
    white-space: nowrap;
    overflow: hidden;
  }
  .file-actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }
  .btn-download {
    background: var(--primary);
    color: #fff;
    border: none;
    border-radius: var(--radius-sm);
    padding: 8px 14px;
    font-size: 13px;
    cursor: pointer;
    text-decoration: none;
    font-family: inherit;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    transition: background 0.2s;
    font-weight: bold;
    white-space: nowrap;
  }
  .btn-download:hover { background: var(--primary-dark); }
  .btn-delete {
    background: #fff0f3;
    color: var(--danger);
    border: 1.5px solid #ffc4cd;
    border-radius: var(--radius-sm);
    padding: 8px 12px;
    font-size: 13px;
    cursor: pointer;
    font-family: inherit;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    transition: background 0.2s, color 0.2s;
    font-weight: bold;
    white-space: nowrap;
  }
  .btn-delete:hover { background: var(--danger); color: #fff; border-color: var(--danger); }

  /* ---- Mobile responsive: stack buttons under filename ---- */
  @media (max-width: 480px) {
    .file-item {
      flex-wrap: wrap;
      align-items: flex-start;
    }
    .file-icon {
      font-size: 24px;
      padding-top: 2px;
    }
    .file-info {
      flex: 1;
      min-width: 0;
    }
    .file-actions {
      width: 100%;
      padding-right: 36px;
      margin-top: 8px;
    }
    .btn-download,
    .btn-delete {
      flex: 1;
      justify-content: center;
      font-size: 13px;
      padding: 9px 8px;
    }
  }

  /* ---- نوتیفیکیشن ---- */
  .toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(80px);
    background: #1e1b4b;
    color: #fff;
    padding: 12px 24px;
    border-radius: var(--radius-sm);
    font-size: 14px;
    transition: transform 0.35s cubic-bezier(.175,.885,.32,1.275);
    z-index: 1000;
    min-width: 200px;
    text-align: center;
  }
  .toast.show { transform: translateX(-50%) translateY(0); }
  .toast.success { background: var(--success-dark); }
  .toast.error { background: var(--danger-dark); }

  /* ---- اسکرول ---- */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 99px; }
"""


class RequestHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        """فرمت لاگ سفارشی"""
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {self.address_string()} - {format % args}")

    def _client_ip(self) -> str:
        """Return the best available client IP."""
        # Respect X-Forwarded-For set by trusted reverse proxy (Parspack)
        forwarded = self.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0]

    def check_auth(self):
        """بررسی احراز هویت با کوکی (token is SHA-256 hash, not raw password)"""
        if "Cookie" in self.headers:
            for cookie in self.headers.get("Cookie").split(";"):
                if cookie.strip() == f"auth={AUTH_TOKEN}":
                    return True
        return False

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def send_html(self, content):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if not self.check_auth():
            self._serve_login(parsed.query)
            return

        if path.startswith("/download/"):
            self._serve_download(path)
        elif path == "/logout":
            self.send_response(302)
            self.send_header("Set-Cookie", "auth=; Max-Age=0; Path=/; HttpOnly")
            self.send_header("Location", "/")
            self.end_headers()
        elif path == "/":
            self._serve_dashboard()
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/login":
            self._handle_login()
        elif path == "/upload":
            if not self.check_auth():
                self.send_error(403, "Forbidden")
                return
            self._handle_upload()
        elif path == "/delete":
            if not self.check_auth():
                self.send_error(403, "Forbidden")
                return
            self._handle_delete()
        else:
            self.send_error(404, "Not found")

    def _serve_login(self, query=""):
        error_html = ""
        if "error=1" in query:
            error_html = """<div class="err-box">🔑 رمز عبور اشتباه است!</div>"""
        if "locked=1" in query:
            error_html = f"""<div class="err-box">🔒 تعداد زیادی تلاش ناموفق. لطفاً {LOCKOUT_SECONDS} ثانیه صبر کنید.</div>"""

        page = f"""<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ورود — {html.escape(SITE_NAME)}</title>
<style>
{CSS}
.login-wrap {{
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #f0f2ff 0%, #e8e4ff 100%);
}}
.login-card {{
  background: #fff;
  border-radius: var(--radius);
  box-shadow: var(--shadow-lg);
  padding: 40px 36px;
  width: 100%;
  max-width: 400px;
  border: 1.5px solid var(--border);
}}
.login-logo {{ text-align: center; font-size: 52px; margin-bottom: 10px; }}
.login-title {{ text-align: center; font-size: 20px; font-weight: bold; color: var(--text); margin-bottom: 6px; }}
.login-sub {{ text-align: center; color: var(--text-muted); font-size: 13px; margin-bottom: 28px; }}
label {{ display: block; font-size: 14px; font-weight: bold; color: var(--text); margin-bottom: 7px; }}
input[type=password] {{
  width: 100%; padding: 12px 16px;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 15px; direction: ltr; text-align: left;
  outline: none; transition: border-color 0.2s;
  font-family: inherit;
}}
input[type=password]:focus {{ border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-light); }}
.submit-btn {{
  width: 100%; margin-top: 18px; padding: 13px;
  background: linear-gradient(90deg, var(--primary) 0%, #a084ee 100%);
  color: #fff; border: none; border-radius: var(--radius-sm);
  font-size: 16px; font-family: inherit; cursor: pointer; font-weight: bold;
  box-shadow: 0 4px 16px rgba(108,99,255,0.25);
  transition: opacity 0.2s;
}}
.submit-btn:hover {{ opacity: 0.9; }}
.err-box {{
  background: #fff0f3; border: 1.5px solid #ffc4cd;
  border-radius: var(--radius-sm); color: var(--danger);
  padding: 10px 16px; font-size: 14px; margin-bottom: 18px; text-align: center;
}}
</style>
</head>
<body>
<div class="login-wrap">
  <div class="login-card">
    <div class="login-logo">☁️</div>
    <div class="login-title">{html.escape(SITE_NAME)}</div>
    <div class="login-sub">برای ورود رمز عبور خود را وارد کنید</div>
    {error_html}
    <form method="POST" action="/login">
      <label>رمز عبور</label>
      <input type="password" name="password" placeholder="••••••••" required autofocus>
      <button type="submit" class="submit-btn">ورود به پنل</button>
    </form>
  </div>
</div>
</body>
</html>"""
        self.send_html(page)

    def _serve_download(self, path):
        raw_name = urllib.parse.unquote(path[len("/download/"):])
        # Sanitise the filename — reject traversal attempts
        filename = os.path.basename(raw_name)
        filepath = _safe_filepath(filename)
        if filepath is None or not os.path.isfile(filepath):
            self.send_error(404, "File not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{urllib.parse.quote(filename)}"')
        self.send_header("Content-Length", str(os.path.getsize(filepath)))
        self.end_headers()
        with open(filepath, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def _serve_dashboard(self):
        files_html = ""
        file_count = 0
        total_size = 0

        if os.path.exists(UPLOAD_DIR):
            entries = sorted(os.listdir(UPLOAD_DIR))
            for fname in entries:
                fpath = os.path.join(UPLOAD_DIR, fname)
                if not os.path.isfile(fpath):
                    continue
                file_count += 1
                fsize = os.path.getsize(fpath)
                total_size += fsize
                date_mod = datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y/%m/%d  %H:%M')
                icon = file_icon(fname)
                safe_name = html.escape(fname)
                enc_name = urllib.parse.quote(fname)
                files_html += f"""
<div class="file-item" id="fi-{html.escape(enc_name)}">
  <div class="file-icon">{icon}</div>
  <div class="file-info">
    <span class="file-name" title="{safe_name}">{safe_name}</span>
    <div class="file-meta">
      <span>📦 {format_size(fsize)}</span>
      <span>🕐 {date_mod}</span>
    </div>
  </div>
  <div class="file-actions">
    <a href="/download/{enc_name}" class="btn-download">⬇️ دانلود</a>
    <button class="btn-delete" onclick="deleteFile('{enc_name}', this)">🗑️ حذف</button>
  </div>
</div>"""

        if not files_html:
            files_html = """
<div class="empty-state">
  <div class="empty-icon">📭</div>
  <p>هنوز هیچ فایلی آپلود نشده است.</p>
</div>"""

        total_str = format_size(total_size)
        count_badge = f'<span class="files-count">{file_count} فایل</span>'
        max_mb_display = html.escape(str(MAX_UPLOAD_SIZE_MB))

        page = f"""<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{html.escape(SITE_NAME)}</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="container">

  <div class="topbar">
    <div class="topbar-title">
      <span class="logo">☁️</span>
      <div>
        <h1>{html.escape(SITE_NAME)}</h1>
        <p>{file_count} فایل · {total_str} فضای استفاده شده</p>
      </div>
    </div>
    <a href="/logout" class="logout-btn">خروج</a>
  </div>

  <div class="card">
    <div class="card-title">📤 آپلود فایل جدید</div>

    <div class="drop-zone" id="dropZone">
      <div class="drop-zone-icon">☁️</div>
      <div class="drop-zone-text">
        فایل را اینجا رها کنید یا <span>انتخاب کنید</span><br>
        <small style="color:#b0aedd">حداکثر {max_mb_display} مگابایت</small>
      </div>
      <input type="file" id="fileInput" onchange="onFileSelect(this)">
    </div>

    <div class="selected-file" id="selectedFile">
      <span id="sfIcon" style="font-size:22px">📁</span>
      <span class="sf-name" id="sfName">—</span>
      <span class="sf-size" id="sfSize">—</span>
    </div>

    <button class="upload-btn" id="uploadBtn" onclick="uploadFile()">⬆️ شروع آپلود</button>

    <div class="progress-wrap" id="progressWrap">
      <div class="progress-track">
        <div class="progress-fill" id="progressFill"></div>
      </div>
      <div class="progress-info">
        <span id="progressPct">0%</span>
        <span id="progressMB">0 MB / 0 MB</span>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title" style="justify-content:space-between">
      <span>📂 فایل‌های ذخیره شده</span>
      {count_badge}
    </div>
    <div id="fileList">{files_html}</div>
  </div>

</div>

<div class="toast" id="toast"></div>

<script>
const MAX_UPLOAD_MB = {MAX_UPLOAD_SIZE_MB};
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');

dropZone.addEventListener('dragover', e => {{ e.preventDefault(); dropZone.classList.add('dragover'); }});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {{
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) {{
    fileInput.files = e.dataTransfer.files;
    onFileSelect(fileInput);
  }}
}});

function onFileSelect(input) {{
  if (!input.files.length) return;
  const f = input.files[0];
  const sel = document.getElementById('selectedFile');
  document.getElementById('sfName').textContent = f.name;
  document.getElementById('sfSize').textContent = formatSize(f.size);
  sel.classList.add('show');
}}

function formatSize(b) {{
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  return (b/1048576).toFixed(2) + ' MB';
}}

function showToast(msg, type='') {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast ' + type + ' show';
  setTimeout(() => t.classList.remove('show'), 3500);
}}

function uploadFile() {{
  if (!fileInput.files.length) {{ showToast('لطفاً یک فایل انتخاب کنید.', 'error'); return; }}
  const file = fileInput.files[0];
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {{
    showToast('حجم فایل نباید بیشتر از ' + MAX_UPLOAD_MB + ' مگابایت باشد.', 'error');
    return;
  }}

  const btn = document.getElementById('uploadBtn');
  const wrap = document.getElementById('progressWrap');
  const fill = document.getElementById('progressFill');
  const pct  = document.getElementById('progressPct');
  const mb   = document.getElementById('progressMB');

  wrap.style.display = 'block';
  btn.disabled = true;

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/upload', true);
  xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name));

  xhr.upload.onprogress = e => {{
    if (e.lengthComputable) {{
      const p = (e.loaded / e.total * 100).toFixed(1);
      fill.style.width = p + '%';
      pct.textContent = p + '%';
      mb.textContent = formatSize(e.loaded) + ' / ' + formatSize(e.total);
    }}
  }};

  xhr.onload = () => {{
    if (xhr.status === 200) {{
      showToast('فایل با موفقیت آپلود شد! ✅', 'success');
      setTimeout(() => window.location.reload(), 1200);
    }} else {{
      showToast('خطا در آپلود فایل: ' + xhr.responseText, 'error');
      btn.disabled = false;
      wrap.style.display = 'none';
    }}
  }};
  xhr.onerror = () => {{ showToast('خطا در ارتباط با سرور.', 'error'); btn.disabled = false; wrap.style.display = 'none'; }};
  xhr.send(file);
}}

function deleteFile(encodedName, btn) {{
  if (!confirm('آیا مطمئن هستید؟ این فایل حذف خواهد شد.')) return;
  btn.disabled = true;
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/delete', true);
  xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  xhr.onload = () => {{
    if (xhr.status === 200) {{
      const row = document.getElementById('fi-' + encodedName);
      if (row) {{ row.style.transition='opacity 0.3s'; row.style.opacity='0'; setTimeout(() => row.remove(), 300); }}
      showToast('فایل حذف شد.', 'success');
    }} else {{
      showToast('خطا در حذف فایل.', 'error');
      btn.disabled = false;
    }}
  }};
  xhr.onerror = () => {{ showToast('خطا در ارتباط.', 'error'); btn.disabled = false; }};
  xhr.send('filename=' + encodedName);
}}
</script>
</body>
</html>"""
        self.send_html(page)

    def _handle_login(self):
        ip = self._client_ip()

        # Brute-force check
        if _check_lockout(ip):
            self.redirect("/?locked=1")
            return

        # Cap login body size to 4 KB to prevent memory abuse
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = min(int(raw_length), 4096)
        except ValueError:
            length = 0

        body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(body)
        password = params.get("password", [""])[0]

        if password == PASSWORD:
            _record_success(ip)
            self.send_response(302)
            # Cookie stores the auth token (hash), NOT the raw password
            self.send_header("Set-Cookie", f"auth={AUTH_TOKEN}; Path=/; HttpOnly; SameSite=Strict")
            self.send_header("Location", "/")
            self.end_headers()
        else:
            _record_failure(ip)
            self.redirect("/?error=1")

    def _handle_upload(self):
        filename_header = self.headers.get("X-File-Name")
        if not filename_header:
            self.send_error(400, "Missing X-File-Name header")
            return

        raw_name = urllib.parse.unquote(filename_header)
        filename = _safe_filename(raw_name)
        if filename is None:
            self.send_error(400, "Invalid or blocked filename")
            return

        # Enforce server-side upload size limit BEFORE touching disk
        raw_cl = self.headers.get("Content-Length", "0")
        try:
            content_length = int(raw_cl)
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return

        if content_length > MAX_UPLOAD_BYTES:
            self.send_error(413, f"File too large. Maximum is {MAX_UPLOAD_SIZE_MB} MB")
            return

        filepath = _safe_filepath(filename)
        if filepath is None:
            self.send_error(400, "Invalid filename")
            return

        # Ensure uploads directory exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        try:
            written = 0
            with open(filepath, "wb") as f:
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    chunk = self.rfile.read(chunk_size)
                    if not chunk:
                        break
                    written += len(chunk)
                    # Double-check we haven't exceeded the limit mid-stream
                    if written > MAX_UPLOAD_BYTES:
                        f.close()
                        os.remove(filepath)
                        self.send_error(413, f"File too large. Maximum is {MAX_UPLOAD_SIZE_MB} MB")
                        return
                    f.write(chunk)
                    remaining -= len(chunk)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except OSError as e:
            # Log a sanitised message; do NOT forward exception text to client
            print(f"[ERROR] Upload failed for file '{filename}': {type(e).__name__}")
            try:
                os.remove(filepath)
            except OSError:
                pass
            self.send_error(500, "Upload failed")

    def _handle_delete(self):
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = min(int(raw_length), 4096)
        except ValueError:
            length = 0

        body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(body)
        raw = params.get("filename", [""])[0]

        filename = _safe_filename(urllib.parse.unquote(raw))
        if filename is None:
            self.send_error(400, "Invalid filename")
            return

        filepath = _safe_filepath(filename)
        if filepath is None or not os.path.isfile(filepath):
            self.send_error(404, "File not found")
            return

        os.remove(filepath)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """سرور چندنخی"""
    daemon_threads = True


if __name__ == "__main__":
    server = ThreadingServer(("0.0.0.0", PORT), RequestHandler)
    print(f"سرور روی پورت {PORT} اجرا شد...")
    print(f"آدرس دسترسی: http://0.0.0.0:{PORT}")
    print(f"نام پروژه: {SITE_NAME}")
    print(f"حداکثر حجم آپلود: {MAX_UPLOAD_SIZE_MB} MB")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nسرور متوقف شد.")
        server.server_close()
