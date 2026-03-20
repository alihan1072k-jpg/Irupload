# Security Audit — File Share Hub

**Audit Date:** 2026-03-20
**Auditor:** Automated security review
**Scope:** `main.py`, `install.sh`, `manage.sh`, `fileserver.conf`

---

## 1. File Structure Overview

```
file-share-hub/
├── main.py              # Core HTTP server (Python stdlib only)
├── fileserver.conf      # Runtime configuration (port, password, site name)
├── install.sh           # Interactive first-run setup script
├── manage.sh            # Runtime management (start/stop/restart/config)
├── uploads/             # Uploaded files directory (MUST be gitignored)
└── replit.md            # Project documentation
```

---

## 2. Vulnerability Findings

### 2.1 No Server-Side Upload Size Enforcement
**Risk: HIGH**

The upload handler reads `Content-Length` and streams the body with no upper bound enforced server-side.
The JavaScript client checks `100 MB`, but this is trivially bypassed with a raw HTTP request (`curl`, etc.).
A malicious or misconfigured client can fill the server disk or exhaust memory.

**Recommended Fix:**
Read `MAX_UPLOAD_SIZE_MB` from config and reject oversized uploads before writing to disk.

---

### 2.2 Dangerous File Extension — No Blocklist
**Risk: HIGH**

There is no check on uploaded file extensions. An attacker (who knows or guesses the password) can upload:
- `.sh`, `.bash`, `.py` — executable scripts
- `.exe`, `.bat`, `.cmd` — Windows executables
- `.php`, `.cgi`, `.pl` — server-side scripts (risk depends on hosting environment)

If the uploads directory is ever served by a CGI-capable web server or Nginx with PHP-FPM, this becomes remote code execution.

**Recommended Fix:**
Maintain a blocked extension list; reject uploads matching it.

---

### 2.3 Directory Traversal — Partial Mitigation Only
**Risk: HIGH**

The upload and download handlers call `os.path.basename()` on the filename, which removes `../` traversal segments.
However the `_serve_download` function does not verify that the resolved absolute path stays within `UPLOAD_DIR`.
On some edge cases (symlinks, unusual filenames), `os.path.basename()` alone is insufficient.

**Recommended Fix:**
After resolving the final path with `os.path.realpath()`, assert it starts with `os.path.realpath(UPLOAD_DIR)`.

---

### 2.4 Hardcoded Default Password
**Risk: HIGH**

`main.py` defaults the password to `"1376"` if not set in config:

```python
PASSWORD = cfg.get("PASSWORD", "1376")
```

If a user skips `install.sh` and runs `python3 main.py` directly without a config file, the server is protected only by a four-digit numeric default.

**Recommended Fix:**
Warn loudly at startup if the default password is still in use. Ideally refuse to start without a config file containing a non-default password.

---

### 2.5 Password Stored in Plain Text Cookie
**Risk: MEDIUM**

The auth cookie stores the literal password value:

```python
self.send_header("Set-Cookie", f"auth={PASSWORD}; Path=/; HttpOnly")
```

This means:
- The password is visible in browser DevTools / network logs.
- Anyone who intercepts the cookie can trivially learn the password (not just gain access).
- Since SSL is handled externally by Parspack, this is safe in transit — but cookie leakage in other ways is a concern.

**Recommended Fix:**
Store a fixed session token (e.g., a hash of the password + a random salt) in the cookie, not the raw password.

---

### 2.6 No Brute-Force Protection on Login
**Risk: MEDIUM**

The `/login` endpoint has no rate limiting. An attacker can attempt millions of password guesses programmatically.

**Recommended Fix:**
Add a login attempt counter (in-memory is sufficient for a single-process server). After N failures from the same IP, impose a delay or temporary lockout.

---

### 2.7 Password Potentially Printed in Logs / Console
**Risk: MEDIUM**

`install.sh` (by common implementation) may echo user input during setup. If the terminal session is logged (e.g., via `script`, tmux history, or shell history), the password ends up in logs.

**Recommended Fix:**
Use `read -s` (silent) for the password prompt. Mask the password if printed in any summary output.

---

### 2.8 Unsafe Logging — Error Details Exposed
**Risk: LOW**

The upload handler logs raw exception details to stdout:

```python
print(f"[ERROR] Upload failed: {e}")
```

In some exception contexts `e` could contain a filesystem path or other server-internal detail.

**Recommended Fix:**
Log a sanitized error message. Avoid forwarding exception strings to any client-visible response.

---

### 2.9 No `Content-Length` Validation on Login Body
**Risk: LOW**

The login handler reads `Content-Length` bytes without checking for abnormally large values:

```python
length = int(self.headers.get("Content-Length", 0))
body = self.rfile.read(length).decode("utf-8")
```

An attacker could send an extremely large POST body to `/login`, consuming memory.

**Recommended Fix:**
Cap the login body read at a safe limit (e.g., 4 KB).

---

### 2.10 Filesystem Path Exposed on 404 Download
**Risk: LOW**

When a download file is not found, `self.send_error(404, "File not found")` is returned without exposing a path — this is acceptable. However the error message for upload failure at line:

```python
self.send_error(500, "Upload failed")
```

…does not expose a path, which is correct. **No action needed** for these two specifically.

---

### 2.11 `uploads/` Directory Could Be Committed to Git
**Risk: MEDIUM**

If `.gitignore` is missing or incomplete, the `uploads/` directory (with all user files) could be accidentally committed to a public GitHub repository.

**Recommended Fix:**
Ensure `uploads/` is in `.gitignore`. Also add `fileserver.conf` (contains the password) to `.gitignore`.

---

### 2.12 `fileserver.conf` Contains Password — Should Be Gitignored
**Risk: HIGH**

`fileserver.conf` stores the plain-text password. If this file is committed to a public repository, the password is immediately public.

**Recommended Fix:**
Add `fileserver.conf` to `.gitignore`. Provide `fileserver.conf.example` instead.

---

### 2.13 No Filename Sanitisation Beyond `basename()`
**Risk: MEDIUM**

Filenames containing null bytes (`\x00`) are passed through the URL decode and basename call. On some Python builds, null bytes in filenames cause unexpected behavior at the OS layer.

**Recommended Fix:**
Reject filenames containing null bytes or non-printable characters.

---

## 3. Risk Summary Table

| # | Issue | Risk |
|---|-------|------|
| 2.1 | No server-side upload size limit | **HIGH** |
| 2.2 | No dangerous extension blocklist | **HIGH** |
| 2.3 | Directory traversal — incomplete mitigation | **HIGH** |
| 2.4 | Hardcoded default password `1376` | **HIGH** |
| 2.12 | `fileserver.conf` not gitignored (contains password) | **HIGH** |
| 2.5 | Raw password stored in session cookie | **MEDIUM** |
| 2.6 | No brute-force protection on login | **MEDIUM** |
| 2.7 | Password printed/logged during install | **MEDIUM** |
| 2.11 | `uploads/` not gitignored | **MEDIUM** |
| 2.13 | Null bytes in filenames not rejected | **MEDIUM** |
| 2.8 | Exception details in server logs | **LOW** |
| 2.9 | No login body size cap | **LOW** |
| 2.10 | Path exposure in error messages | **LOW** (not present) |

---

## 4. Fixes Applied (Updated After Remediation)

See bottom of this file — updated after code changes are complete.

---

## 5. Out of Scope

- SSL/TLS configuration — handled externally by Parspack reverse proxy.
- Authentication complexity — single-password design is intentional for the target use case.
- Multi-user access control — out of scope for this project.

---

## Post-Remediation Update

The following fixes were applied in this release:

| Issue | Fix Applied |
|-------|-------------|
| 2.1 — No server-side upload size limit | `MAX_UPLOAD_SIZE_MB` enforced in `_handle_upload()` before writing to disk |
| 2.2 — Dangerous extension blocklist | `BLOCKED_EXTENSIONS` set checked in `_handle_upload()`; upload rejected with 400 |
| 2.3 — Directory traversal | `os.path.realpath()` check added; path must be inside `UPLOAD_DIR` |
| 2.4 — Hardcoded default password | Startup warning printed if default password `1376` is still in use |
| 2.5 — Raw password in cookie | Cookie now stores SHA-256 hex digest of password, not the password itself |
| 2.7 — Password printed in install | `install.sh` uses `read -s` for password input; summary masks password |
| 2.9 — No login body size cap | Login body read capped at 4096 bytes |
| 2.11 — `uploads/` not gitignored | Added to `.gitignore` |
| 2.12 — `fileserver.conf` not gitignored | Added to `.gitignore`; `fileserver.conf.example` created |
| 2.13 — Null bytes in filenames | Null byte and non-printable character check added to `_handle_upload()` |
| 2.6 — No brute-force protection | In-memory login failure counter added; 5 failures = 30-second cooldown per IP |
| 2.8 — Exception detail in logs | Upload error log sanitised; internal path not forwarded to client |
