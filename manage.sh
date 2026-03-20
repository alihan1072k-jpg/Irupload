#!/usr/bin/env bash
# =============================================================================
#  File Share Hub — Server Manager
#  Usage: bash manage.sh   or   upfile  (if alias is configured)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/fileserver.conf"
PID_FILE="$SCRIPT_DIR/fileserver.pid"
MAIN_PY="$SCRIPT_DIR/main.py"
LOG_FILE="$SCRIPT_DIR/server.log"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
YLW='\033[1;33m'
GRN='\033[0;32m'
CYN='\033[0;36m'
BLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

ok()   { echo -e "  ${GRN}v${NC}  $*"; }
warn() { echo -e "  ${YLW}!${NC}  $*"; }
fail() { echo -e "  ${RED}x${NC}  $*"; }

box() {
    local w=51
    echo -e "${CYN}+-------------------------------------------------+${NC}"
    while IFS= read -r line; do
        printf "${CYN}|${NC} ${BLD}%-*s${NC}${CYN}|${NC}\n" $(( w - 2 )) "$line"
    done <<< "$1"
    echo -e "${CYN}+-------------------------------------------------+${NC}"
}

divider() { echo -e "${DIM}  ─────────────────────────────────────────────────${NC}"; }

# ── Config helpers ────────────────────────────────────────────────────────────
get_conf() {
    grep -E "^${1}=" "$CONFIG_FILE" 2>/dev/null | tail -1 | cut -d= -f2-
}

set_conf() {
    local key="$1" val="$2"
    if grep -qE "^${key}=" "$CONFIG_FILE" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${val}|" "$CONFIG_FILE"
    else
        echo "${key}=${val}" >> "$CONFIG_FILE"
    fi
}

# ── Process helpers ───────────────────────────────────────────────────────────
is_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

do_stop() {
    if is_running; then
        kill "$(cat "$PID_FILE")" 2>/dev/null
        rm -f "$PID_FILE"
        ok "Server stopped."
    else
        warn "Server is not running."
    fi
}

do_start() {
    if is_running; then
        warn "Already running  (PID: $(cat "$PID_FILE"))."
        return
    fi
    nohup python3 "$MAIN_PY" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    ok "Server started  (PID: $(cat "$PID_FILE"))."
    ok "Log: $LOG_FILE"
}

# ── Menu ──────────────────────────────────────────────────────────────────────
clear
echo ""
box "  File Share Hub  --  Server Manager"
echo ""

# Live status line
if is_running; then
    PORT_VAL="$(get_conf PORT)"
    echo -e "  Status  ${GRN}RUNNING${NC}  PID: $(cat "$PID_FILE")   Port: ${PORT_VAL:-5000}"
else
    echo -e "  Status  ${RED}STOPPED${NC}"
fi

echo ""
divider
echo ""
echo -e "    ${BLD}1)${NC}  Change password"
echo -e "    ${BLD}2)${NC}  Change port"
echo -e "    ${BLD}3)${NC}  Change site name"
echo -e "    ${BLD}4)${NC}  Change max upload size"
echo ""
echo -e "    ${BLD}5)${NC}  Restart server"
echo -e "    ${BLD}6)${NC}  Stop server"
echo -e "    ${BLD}7)${NC}  Start server"
echo -e "    ${BLD}8)${NC}  Show status"
echo ""
echo -e "    ${BLD}9)${NC}  ${RED}Delete project${NC}  ${DIM}(removes all files)${NC}"
echo -e "    ${BLD}0)${NC}  Exit"
echo ""
divider
echo ""
read -r -p "  Your choice: " CHOICE
echo ""

case "$CHOICE" in

    1)  # ── Change password ───────────────────────────────────────────────────
        warn "Characters will not be displayed while typing."
        echo ""
        while true; do
            read -r -s -p "  New password (min 6 chars): " NEW_PASS; echo ""
            if [ -z "$NEW_PASS" ]; then
                fail "Password cannot be empty."; continue
            fi
            if [ "${#NEW_PASS}" -lt 6 ]; then
                fail "Must be at least 6 characters."; continue
            fi
            read -r -s -p "  Confirm new password:       " CONFIRM_PASS; echo ""
            if [ "$NEW_PASS" != "$CONFIRM_PASS" ]; then
                fail "Passwords do not match. Try again."; echo ""
            else
                break
            fi
        done
        set_conf "PASSWORD" "$NEW_PASS"
        ok "Password updated. Restart the server to apply."
        ;;

    2)  # ── Change port ───────────────────────────────────────────────────────
        while true; do
            read -r -p "  New port [1-65535]: " NEW_PORT
            if [[ "$NEW_PORT" =~ ^[0-9]+$ ]] && [ "$NEW_PORT" -ge 1 ] && [ "$NEW_PORT" -le 65535 ]; then
                break
            else
                fail "Invalid port number."
            fi
        done
        set_conf "PORT" "$NEW_PORT"
        ok "Port changed to $NEW_PORT. Restart the server to apply."
        ;;

    3)  # ── Change site name ──────────────────────────────────────────────────
        read -r -p "  New site name: " NEW_NAME
        if [ -n "$NEW_NAME" ]; then
            set_conf "SITE_NAME" "$NEW_NAME"
            ok "Site name changed to '$NEW_NAME'. Restart to apply."
        else
            fail "Site name cannot be empty."
        fi
        ;;

    4)  # ── Change max upload size ────────────────────────────────────────────
        while true; do
            read -r -p "  Max upload size in MB [1-5000]: " NEW_MAX
            if [[ "$NEW_MAX" =~ ^[0-9]+$ ]] && [ "$NEW_MAX" -ge 1 ] && [ "$NEW_MAX" -le 5000 ]; then
                break
            else
                fail "Must be a number between 1 and 5000."
            fi
        done
        set_conf "MAX_UPLOAD_SIZE_MB" "$NEW_MAX"
        ok "Max upload size set to ${NEW_MAX} MB. Restart to apply."
        ;;

    5)  # ── Restart ───────────────────────────────────────────────────────────
        do_stop
        sleep 1
        do_start
        ;;

    6)  # ── Stop ──────────────────────────────────────────────────────────────
        do_stop
        ;;

    7)  # ── Start ─────────────────────────────────────────────────────────────
        do_start
        ;;

    8)  # ── Status ────────────────────────────────────────────────────────────
        if is_running; then
            PORT_VAL="$(get_conf PORT)"
            SITE_VAL="$(get_conf SITE_NAME)"
            MAX_VAL="$(get_conf MAX_UPLOAD_SIZE_MB)"
            echo ""
            box "  Status   : RUNNING
  PID      : $(cat "$PID_FILE")
  Port     : ${PORT_VAL:-5000}
  Site     : ${SITE_VAL:-File Share Hub}
  Max size : ${MAX_VAL:-200} MB"
        else
            warn "Server is not running."
        fi
        ;;

    9)  # ── Delete project ────────────────────────────────────────────────────
        echo ""
        warn "This will permanently delete all project files and uploads."
        warn "This action cannot be undone."
        echo ""
        read -r -p "  Type YES to confirm: " CONFIRM_DEL
        if [ "$CONFIRM_DEL" == "YES" ]; then
            do_stop
            rm -rf "$SCRIPT_DIR"
            echo ""
            echo "  Project removed."
        else
            ok "Cancelled. Nothing was deleted."
        fi
        ;;

    0)  exit 0 ;;

    *)  fail "Invalid choice." ;;

esac

echo ""
