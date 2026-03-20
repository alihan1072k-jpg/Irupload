#!/usr/bin/env bash
# =============================================================================
#  File Share Hub — Setup Script
#  Run once to configure and start your file server.
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/fileserver.conf"
PID_FILE="$SCRIPT_DIR/fileserver.pid"
UPLOAD_DIR="$SCRIPT_DIR/uploads"
MANAGE_SCRIPT="$SCRIPT_DIR/manage.sh"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
YLW='\033[1;33m'
GRN='\033[0;32m'
CYN='\033[0;36m'
BLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Helpers ───────────────────────────────────────────────────────────────────
ok()   { echo -e "  ${GRN}v${NC}  $*"; }
warn() { echo -e "  ${YLW}!${NC}  $*"; }
fail() { echo -e "  ${RED}x${NC}  $*"; }

box() {
    local w=51
    local top="+-------------------------------------------------+"
    local bot="+-------------------------------------------------+"
    echo -e "${CYN}${top}${NC}"
    while IFS= read -r line; do
        local pad=$(( w - 2 - ${#line} ))
        printf "${CYN}|${NC} ${BLD}%-*s${NC}${CYN}|${NC}\n" $(( w - 2 )) "$line"
    done <<< "$1"
    echo -e "${CYN}${bot}${NC}"
}

divider() { echo -e "${DIM}  ─────────────────────────────────────────────────${NC}"; }
section()  { echo ""; divider; echo -e "  ${BLD}$1${NC}"; divider; echo ""; }

# ── Header ────────────────────────────────────────────────────────────────────
clear
echo ""
box "  File Share Hub  --  Setup Wizard
  Self-hosted file server for restricted networks"
echo ""

# ── Step 1 — Port ─────────────────────────────────────────────────────────────
section "[1/5]  Server Port"
while true; do
    read -r -p "  Enter port number [default: 5000]: " USER_PORT
    USER_PORT="${USER_PORT:-5000}"
    if [[ "$USER_PORT" =~ ^[0-9]+$ ]] && [ "$USER_PORT" -ge 1 ] && [ "$USER_PORT" -le 65535 ]; then
        ok "Port set to $USER_PORT"
        break
    else
        fail "Must be a number between 1 and 65535. Try again."
    fi
done

# ── Step 2 — Site name ────────────────────────────────────────────────────────
section "[2/5]  Display Name"
read -r -p "  Site name [default: My File Server]: " USER_SITE_NAME
USER_SITE_NAME="${USER_SITE_NAME:-My File Server}"
ok "Display name: $USER_SITE_NAME"

# ── Step 3 — Password ─────────────────────────────────────────────────────────
section "[3/5]  Password"
warn "Characters will not be displayed while typing."
echo ""
while true; do
    read -r -s -p "  Password (min 6 chars): " USER_PASSWORD
    echo ""
    if [ -z "$USER_PASSWORD" ]; then
        fail "Password cannot be empty."; continue
    fi
    if [ "${#USER_PASSWORD}" -lt 6 ]; then
        fail "Password must be at least 6 characters."; continue
    fi
    read -r -s -p "  Confirm password:       " USER_PASSWORD_CONFIRM
    echo ""
    if [ "$USER_PASSWORD" != "$USER_PASSWORD_CONFIRM" ]; then
        fail "Passwords do not match. Try again."; echo ""
    else
        ok "Password saved."
        break
    fi
done

# ── Step 4 — Run mode ─────────────────────────────────────────────────────────
section "[4/5]  Run Mode"
echo -e "    ${BLD}1)${NC} Foreground  ${DIM}-- stays in terminal, good for testing${NC}"
echo -e "    ${BLD}2)${NC} Background  ${DIM}-- runs via nohup, survives terminal close${NC}"
echo ""
while true; do
    read -r -p "  Select [1/2, default: 1]: " USER_RUN_MODE
    USER_RUN_MODE="${USER_RUN_MODE:-1}"
    if [[ "$USER_RUN_MODE" == "1" || "$USER_RUN_MODE" == "2" ]]; then
        break
    else
        fail "Please enter 1 or 2."
    fi
done

# ── Step 5 — Max upload size ──────────────────────────────────────────────────
section "[5/5]  Maximum Upload Size"
while true; do
    read -r -p "  Max file size in MB [default: 200, range: 1-5000]: " USER_MAX_SIZE
    USER_MAX_SIZE="${USER_MAX_SIZE:-200}"
    if [[ "$USER_MAX_SIZE" =~ ^[0-9]+$ ]] && [ "$USER_MAX_SIZE" -ge 1 ] && [ "$USER_MAX_SIZE" -le 5000 ]; then
        ok "Max upload: ${USER_MAX_SIZE} MB"
        break
    else
        fail "Must be a number between 1 and 5000."
    fi
done

# ── Write config ──────────────────────────────────────────────────────────────
cat > "$CONFIG_FILE" << EOF
# File Share Hub -- Configuration
# Generated on $(date '+%Y-%m-%d %H:%M:%S')

PORT=$USER_PORT
SITE_NAME=$USER_SITE_NAME
PASSWORD=$USER_PASSWORD
MAX_UPLOAD_SIZE_MB=$USER_MAX_SIZE
EOF

chmod 600 "$CONFIG_FILE"
mkdir -p "$UPLOAD_DIR"
chmod 755 "$UPLOAD_DIR"

# ── Summary ───────────────────────────────────────────────────────────────────
RUN_MODE_LABEL="Foreground"
[ "$USER_RUN_MODE" == "2" ] && RUN_MODE_LABEL="Background (nohup)"

echo ""
box "  Setup complete!

  Port        : $USER_PORT
  Site name   : $USER_SITE_NAME
  Password    : ........  (hidden)
  Max upload  : ${USER_MAX_SIZE} MB
  Run mode    : $RUN_MODE_LABEL"
echo ""

# ── Optional alias ────────────────────────────────────────────────────────────
if [ -f "$MANAGE_SCRIPT" ]; then
    chmod +x "$MANAGE_SCRIPT"
    read -r -p "  Add 'upfile' shortcut to ~/.bashrc? [y/N]: " ADD_ALIAS
    echo ""
    if [[ "$ADD_ALIAS" =~ ^[Yy]$ ]]; then
        ALIAS_LINE="alias upfile='bash $MANAGE_SCRIPT'"
        if ! grep -qF "$ALIAS_LINE" ~/.bashrc 2>/dev/null; then
            echo "$ALIAS_LINE" >> ~/.bashrc
            ok "Shortcut added. Run: source ~/.bashrc"
        else
            ok "Shortcut already exists in ~/.bashrc."
        fi
    fi
fi

# ── Start ─────────────────────────────────────────────────────────────────────
divider
echo ""
if [ "$USER_RUN_MODE" == "2" ]; then
    nohup python3 "$SCRIPT_DIR/main.py" >> "$SCRIPT_DIR/server.log" 2>&1 &
    echo $! > "$PID_FILE"
    ok "Server running in background   PID: $(cat "$PID_FILE")"
    ok "Log  : $SCRIPT_DIR/server.log"
    ok "Manage server: bash manage.sh"
else
    ok "Starting server on port $USER_PORT ..."
    warn "Press Ctrl+C to stop."
    echo ""
    divider
    echo ""
    python3 "$SCRIPT_DIR/main.py"
fi
