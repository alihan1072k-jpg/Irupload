# ☁️ File Share Hub

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
git clone https://github.com/YOUR_USERNAME/file-share-hub.git
cd file-share-hub
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

If you'd rather skip the wizard:

```bash
cp fileserver.conf.example fileserver.conf
nano fileserver.conf        # set PORT, PASSWORD, etc.
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

> `fileserver.conf` is in `.gitignore`. It will not be pushed to any repository.

To update settings after installation, edit the file directly or run `bash manage.sh`.

---

## Managing the server

```bash
bash manage.sh
```

Or use the `upfile` shortcut if you added it during setup:

```bash
upfile
```

The manager lets you:

- Change password, port, site name, or upload limit
- Start, stop, or restart the server
- Check live server status
- Remove the project entirely

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

Works fine with Nginx, Caddy, or Parspack's reverse proxy.

---

## Project layout

```
file-share-hub/
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
