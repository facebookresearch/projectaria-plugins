#!/bin/bash
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ═══════════════════════════════════════════════════════════════
# Web App Creator — Data Streaming Server (Double-click to launch!)
# ═══════════════════════════════════════════════════════════════
# macOS .command file — double-click in Finder to run.
# Starts Aria device streaming + WebSocket data server (port 17300).
# Press Ctrl+C in the Terminal window to stop everything.
# ═══════════════════════════════════════════════════════════════

# ── Resolve project directory from this script's location ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
cd "$PROJECT_DIR"

# ── Project Aria Brand Colors (24-bit True Color ANSI) ──
RESET="\033[0m"
BOLD="\033[1m"
DIM="\033[2m"
ITALIC="\033[3m"

# Primary Palette
TEAL="\033[38;2;24;238;212m"        # #18EED4  Primary accent
META_BLUE="\033[38;2;0;100;224m"    # #0064E0  CTA / active
BROWN="\033[38;2;44;13;0m"          # #2C0D00  Deep brown

# Text on LIGHT terminal background (dark Aria brand colours)
TXT="\033[38;2;28;43;51m"           # #1C2B33  Primary text (dark)
TXT_SEC="\033[38;2;52;72;84m"       # #344854  Secondary text
TXT_BODY="\033[38;2;70;90;105m"     # #465A69  Body
TXT_LABEL="\033[38;2;67;67;67m"     # #434343  Muted
TXT_CAP="\033[38;2;70;90;105m"      # #465A69  Caption (= body, readable on light bg)
LINK="\033[38;2;56;137;234m"        # #3889EA  Link blue

# Text on DARK banner backgrounds (light colours)
WHITE="\033[38;2;255;255;255m"      # #FFFFFF  White
LIGHT="\033[38;2;247;245;242m"      # #F7F5F2  Off-white (for dark bg only)

# Semantic
OK="\033[38;2;0;140;120m"           # Darker teal for light bg readability
ERR="\033[38;2;220;50;47m"          # Error    = Red
WARN="\033[38;2;180;120;30m"        # Warning  = Warm amber (darker for light bg)

# Backgrounds
BG_HERO="\033[48;2;44;13;0m"        # #2C0D00  Hero bg
BG_DARK="\033[48;2;12;41;47m"       # #0C292F  Dark teal section
EOL="\033[K"                         # Erase to end of line (fills bg color to right edge)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Diagnostic log setup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
STARTUP_LOG="$LOG_DIR/aria_startup.log"
WS_LOG="$LOG_DIR/aria_websocket.log"

# ── Log rotation: keep only the previous session ──
[ -f "$STARTUP_LOG" ] && mv -f "$STARTUP_LOG" "$LOG_DIR/aria_startup.prev.log"
[ -f "$WS_LOG" ]      && mv -f "$WS_LOG"      "$LOG_DIR/aria_websocket.prev.log"

# log() — write timestamped line to terminal AND startup log
log() {
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    # Strip ANSI colour codes for the log file
    local plain
    plain="$(echo -e "$*" | sed $'s/\033\\[[0-9;]*m//g')"
    echo "[$ts] $plain" >> "$STARTUP_LOG"
    echo -e "  $*"
}

# log_file() — write to log file only (no terminal output)
log_file() {
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    local plain
    plain="$(echo -e "$*" | sed $'s/\033\\[[0-9;]*m//g')"
    echo "[$ts] $plain" >> "$STARTUP_LOG"
}

# step_start / step_done — timing helpers
step_start() {
    STEP_T0="$(date +%s)"
    log "$@"
}
step_done() {
    local elapsed=$(( $(date +%s) - STEP_T0 ))
    log "$@ (${elapsed}s)"
}

# ── Terminal title ──
echo -ne "\033]0;⚡ Web App Creator — Backend Services\007"

# ── Hero Banner (bg: Deep Brown #2C0D00) ──
echo ""
echo -e "${BG_HERO}${EOL}${RESET}"
echo -e "${BG_HERO}    ${TEAL}${BOLD}WEB APP CREATOR${RESET}${BG_HERO}${EOL}${RESET}"
echo -e "${BG_HERO}${EOL}${RESET}"
echo -e "${BG_HERO}   ${WHITE}${BOLD}⚡ Backend Services${RESET}${BG_HERO}${LIGHT}                        WebSocket on :17300${EOL}${RESET}"
echo -e "${BG_HERO}${EOL}${RESET}"
echo ""
echo -e "  ${TXT_BODY}📂 ${TXT}$PROJECT_DIR${RESET}"
echo ""
echo -e "  ${WARN}${BOLD}⚠️  IMPORTANT: Make sure your Aria glasses are connected via USB and switched on!${RESET}"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Environment snapshot (logged before any setup)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
log_file "════════════════════════════════════════════════"
log_file "  Web App Creator — Startup Diagnostic Log"
log_file "════════════════════════════════════════════════"
log_file "Date/Time : $(date)"
log_file "Project   : $PROJECT_DIR"
log_file "macOS     : $(sw_vers -productVersion 2>/dev/null || echo 'unknown') ($(uname -m))"
log_file "Python3   : $(which python3 2>/dev/null || echo 'NOT FOUND') — $(python3 --version 2>/dev/null || echo 'N/A')"
log_file "Disk free : $(df -h . 2>/dev/null | tail -1 | awk '{print $4}') available"
log_file "Shell     : $SHELL ($BASH_VERSION)"
log_file "════════════════════════════════════════════════"

# ── Internal Meta environment hint (one-liner) ──
if command -v buck2 &>/dev/null || command -v ariane &>/dev/null; then
    echo -e "  ${TXT_CAP}${ITALIC}ℹ Internal Meta environment detected — this launcher uses the public${RESET}"
    echo -e "  ${TXT_CAP}${ITALIC}  projectaria-client-sdk; for buck2/Ariane workflows see the ARK skill.${RESET}"
    echo ""
    log_file "INFO: Internal Meta environment detected (buck2/ariane present)"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Pre-flight checks
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── Remove macOS quarantine flags (first run only) ──
QUARANTINE_DONE="$LOG_DIR/quarantine_cleared"
step_start "${META_BLUE}${BOLD}[1/7]${RESET} ${TXT_CAP}🔓 Checking macOS quarantine flags...${RESET}"
if [ -f "$QUARANTINE_DONE" ]; then
    step_done "${OK}✔ Already cleared (skipped)${RESET}"
else
    if xattr -lr "$PROJECT_DIR" 2>/dev/null | grep -q "com.apple.quarantine"; then
        log "${WARN}🔓 Quarantine flags detected — removing...${RESET}"
        xattr -rd com.apple.quarantine "$PROJECT_DIR" 2>/dev/null
        step_done "${OK}✔ Quarantine flags removed${RESET}"
    else
        step_done "${OK}✔ No quarantine flags (clean)${RESET}"
    fi
    touch "$QUARANTINE_DONE"
fi

# ── Check python3 (require 3.12 for projectaria-client-sdk wheel compatibility) ──
step_start "${META_BLUE}${BOLD}[2/7]${RESET} ${TXT_CAP}🐍 Checking Python 3.12 (required by Aria SDK)...${RESET}"
PYTHON_BIN=""
for candidate in python3.12; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON_BIN="$(command -v "$candidate")"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    log "${WARN}⚠ Python 3.12 not found — required for projectaria-client-sdk${RESET}"
    if command -v brew &>/dev/null; then
        log "${WARN}  Homebrew detected — installing Python 3.12 automatically...${RESET}"
        log_file "Attempting: brew install python@3.12"
        brew install python@3.12 >> "$STARTUP_LOG" 2>&1
        if command -v python3.12 &>/dev/null; then
            PYTHON_BIN="$(command -v python3.12)"
            log "${OK}  ✔ Python 3.12 installed via Homebrew${RESET}"
            log_file "OK: Python 3.12 installed — $("$PYTHON_BIN" --version 2>&1)"
        else
            log "${ERR}  ✖ Installation failed. Please install Python 3.12 manually:${RESET}"
            log_file "FAIL: brew install python@3.12 failed"
            echo -e "  ${TXT_CAP}    • ${LINK}brew install python@3.12${RESET}"
            echo -e "  ${TXT_CAP}    • ${LINK}https://www.python.org/downloads/${RESET}"
            echo ""; echo "Press any key to close..."; read -n1; exit 1
        fi
    else
        log "${ERR}${BOLD}✖ Python 3.12 not found.${RESET}"
        log_file "FAIL: python3.12 not found, no brew"
        echo ""
        echo -e "  ${TXT}${BOLD}Easiest path (recommended for most users):${RESET}"
        echo -e "  ${TXT_CAP}    1. Open this link: ${LINK}https://www.python.org/downloads/release/python-3128/${RESET}"
        echo -e "  ${TXT_CAP}    2. Download the macOS 64-bit universal2 ${BOLD}.pkg${RESET}${TXT_CAP} installer"
        echo -e "  ${TXT_CAP}    3. Double-click the .pkg, follow the wizard (takes ~1 min)"
        echo -e "  ${TXT_CAP}    4. Re-run this launcher${RESET}"
        echo ""
        echo -e "  ${TXT}${BOLD}Developer path (if you have Homebrew):${RESET}"
        echo -e "  ${TXT_CAP}    • ${LINK}brew install python@3.12${RESET}"
        echo ""
        echo "Press any key to close..."; read -n1; exit 1
    fi
else
    step_done "${OK}✔ Using $("$PYTHON_BIN" --version 2>&1) ($PYTHON_BIN)${RESET}"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 0: First-time setup (auto-install)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── Ensure a working venv exists (must match selected Python version) ──
step_start "${META_BLUE}${BOLD}[3/7]${RESET} ${TXT_CAP}📦 Checking Python venv...${RESET}"
NEED_VENV=false
VENV_PYTHON_VER=""
if [ -d "$PROJECT_DIR/venv" ]; then
    VENV_PYTHON_VER=$("$PROJECT_DIR/venv/bin/python3" --version 2>/dev/null || echo "")
fi

if [ ! -d "$PROJECT_DIR/venv" ]; then
    log_file "venv directory not found — will create"
    NEED_VENV=true
elif [ -z "$VENV_PYTHON_VER" ]; then
    log "${WARN}⚠ Existing venv is broken (wrong interpreter path) — recreating...${RESET}"
    log_file "venv broken: $(ls -la "$PROJECT_DIR/venv/bin/python3" 2>&1)"
    rm -rf "$PROJECT_DIR/venv"
    NEED_VENV=true
elif [ "$VENV_PYTHON_VER" != "$("$PYTHON_BIN" --version 2>&1)" ]; then
    log "${WARN}⚠ Existing venv uses ${VENV_PYTHON_VER} but need $("$PYTHON_BIN" --version 2>&1) — recreating...${RESET}"
    log_file "venv Python mismatch: venv=$VENV_PYTHON_VER, selected=$("$PYTHON_BIN" --version 2>&1)"
    rm -rf "$PROJECT_DIR/venv"
    NEED_VENV=true
fi

if $NEED_VENV; then
    log "${WARN}📦 First-time setup: Creating Python venv with $("$PYTHON_BIN" --version 2>&1)...${RESET}"
    "$PYTHON_BIN" -m venv "$PROJECT_DIR/venv"
    log "${OK}✔ venv created${RESET}"
    NEED_DEPS=true
else
    step_done "${OK}✔ venv OK${RESET}"
    NEED_DEPS=false
fi

source "$PROJECT_DIR/venv/bin/activate"

if $NEED_DEPS || ! "$PROJECT_DIR/venv/bin/python3" -c "import websockets" &>/dev/null; then
    step_start "${WARN}📦 Installing Python dependencies (this may take 2 minutes)...${RESET}"
    log_file "--- pip upgrade output ---"
    "$PROJECT_DIR/venv/bin/pip" install --upgrade pip >> "$STARTUP_LOG" 2>&1
    log_file "--- pip install requirements output ---"

    # Run pip install in background so we can show a spinner
    "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt" >> "$STARTUP_LOG" 2>&1 &
    PIP_PID=$!

    # Animated spinner while pip runs
    SPINNER_CHARS='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    TICK=0
    ELAPSED=0
    while kill -0 $PIP_PID 2>/dev/null; do
        i=$(( TICK % ${#SPINNER_CHARS} ))
        char="${SPINNER_CHARS:$i:1}"
        echo -ne "  ${OK}${char}${RESET} ${TXT_CAP}Installing packages... ${DIM}(${ELAPSED}s)${RESET}  \r"
        sleep 0.25
        TICK=$((TICK + 1))
        ELAPSED=$((TICK / 4))
    done

    wait $PIP_PID
    PIP_EXIT=$?
    echo -ne "\033[2K\r"  # clear spinner line

    if [ $PIP_EXIT -eq 0 ]; then
        step_done "${OK}✔ Python deps installed${RESET}"
    else
        log "${ERR}✖ pip install failed (exit code $PIP_EXIT) — see $STARTUP_LOG${RESET}"
        log_file "FAIL: pip install exited with code $PIP_EXIT"
        echo ""; echo "Press any key to close..."; read -n1; exit 1
    fi
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# adb PATH setup (3-tier fallback: bundled → system → hard error)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# aria_gen2 is a C++ binary that talks to glasses via USB through adb. Without
# adb on PATH, every aria_gen2 command silently exits 0 and writes no output —
# the same failure mode that bit us in v2.7.7 ("empty CLI output for every
# command"). projectaria-client-sdk bundles a universal-binary adb inside the
# wheel at venv/lib/.../aria/tools/adb — we prefer that to avoid touching the
# user's system adb (Android Studio, Homebrew, etc.).
step_start "${META_BLUE}${BOLD}[4/7]${RESET} ${TXT_CAP}🔌 Locating adb (USB transport for aria_gen2)...${RESET}"
ADB_TOOLS_DIR=""
if [ -d "$PROJECT_DIR/venv" ]; then
    # -maxdepth 8 covers the typical layout (venv/lib/pythonX.YY/site-packages/aria/tools/adb)
    # without requiring a slow full-tree search. First hit wins.
    ADB_PATH=$(find "$PROJECT_DIR/venv" -maxdepth 8 -type f -name adb 2>/dev/null | head -1)
    if [ -n "$ADB_PATH" ] && [ -x "$ADB_PATH" ]; then
        ADB_TOOLS_DIR="$(dirname "$ADB_PATH")"
    fi
fi

if [ -n "$ADB_TOOLS_DIR" ]; then
    export PATH="$ADB_TOOLS_DIR:$PATH"
    log_file "Using bundled adb: $ADB_TOOLS_DIR/adb"
    # Verify it actually runs (catches arch mismatch, Gatekeeper quarantine, etc.)
    if ! "$ADB_TOOLS_DIR/adb" version >> "$STARTUP_LOG" 2>&1; then
        log "${WARN}⚠ Bundled adb found but won't execute — trying system adb${RESET}"
        log_file "Bundled adb at $ADB_TOOLS_DIR/adb failed to run"
        ADB_TOOLS_DIR=""
    else
        step_done "${OK}✔ Using bundled adb${RESET}"
    fi
fi

if [ -z "$ADB_TOOLS_DIR" ]; then
    if command -v adb &>/dev/null; then
        step_done "${OK}✔ Using system adb: $(command -v adb)${RESET}"
        log_file "Using system adb: $(command -v adb)"
    else
        log "${ERR}${BOLD}✖ No working adb found${RESET}"
        log_file "FAIL: no bundled adb (pip install incomplete?) and no system adb"
        echo ""
        echo -e "  ${ERR}${BOLD}🔌 USB transport (adb) is missing${RESET}"
        echo ""
        echo -e "  ${TXT}    aria_gen2 needs adb to talk to glasses over USB. Without it, every"
        echo -e "  ${TXT}    command silently exits 0 with no output, and nothing will work.${RESET}"
        echo ""
        echo -e "  ${TXT}${BOLD}Fix:${RESET}"
        echo -e "  ${TXT_CAP}    1. The bundled adb usually ships inside the venv. Try wiping the venv"
        echo -e "  ${TXT_CAP}       and letting this launcher rebuild it from scratch:${RESET}"
        echo -e "  ${LINK}         rm -rf '$PROJECT_DIR/venv'${RESET}"
        echo -e "  ${TXT_CAP}       then re-run this launcher.${RESET}"
        echo ""
        echo -e "  ${TXT_CAP}    2. Or install system adb (one-off, requires Homebrew):${RESET}"
        echo -e "  ${LINK}         brew install android-platform-tools${RESET}"
        echo ""
        echo "Press any key to close..."; read -n1; exit 1
    fi
fi

echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Clean up old processes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

step_start "${META_BLUE}${BOLD}[5/7]${RESET} ${TXT_CAP}🧹 Cleaning up old processes on ports 17300, 6768...${RESET}"
OLD_PIDS=$(lsof -ti:17300,6768 2>/dev/null || true)
if [ -n "$OLD_PIDS" ]; then
    log_file "Killing PIDs on ports 17300/6768: $OLD_PIDS"
    echo "$OLD_PIDS" | xargs kill -9 2>/dev/null || true
    sleep 1
    step_done "${OK}✔ Old processes killed (PIDs: $OLD_PIDS)${RESET}"
else
    step_done "${OK}✔ Ports clear${RESET}"
fi
echo ""

# ── Cleanup on Ctrl+C ──
# Terminal close is handled by Python's orphan detection (websocket_bridge.py).
ARIA_CLI="$PROJECT_DIR/venv/bin/aria_gen2"

cleanup() {
    trap - SIGINT SIGTERM SIGHUP
    echo ""
    echo -e "  ${ERR}${BOLD}🛑 Stopping all services...${RESET}"
    log_file "Shutdown initiated (Ctrl+C)"

    # 1. Kill Python process IMMEDIATELY by saved PID (don't let it compete)
    if [ -n "$WEBSOCKET_PID" ] && kill -0 "$WEBSOCKET_PID" 2>/dev/null; then
        kill -9 "$WEBSOCKET_PID" 2>/dev/null || true
        wait "$WEBSOCKET_PID" 2>/dev/null || true
        log_file "Killed WebSocket process PID=$WEBSOCKET_PID"
    fi

    # 2. Stop glasses streaming (run in background with manual timeout)
    if [ -x "$ARIA_CLI" ]; then
        "$ARIA_CLI" streaming stop >> "$STARTUP_LOG" 2>&1 &
        local stop_pid=$!
        local waited=0
        while kill -0 "$stop_pid" 2>/dev/null && [ $waited -lt 3 ]; do
            sleep 1
            waited=$((waited + 1))
        done
        kill -9 "$stop_pid" 2>/dev/null || true
        wait "$stop_pid" 2>/dev/null || true
        log_file "aria_gen2 streaming stop completed (waited ${waited}s)"
    fi

    # 3. Final sweep — kill anything still on our ports
    lsof -ti:17300,6768 2>/dev/null | xargs kill -9 2>/dev/null || true

    echo -e "  ${OK}✔ All services stopped.${RESET}"
    log_file "Shutdown complete"
    echo ""

    while true; do
        echo -e "  ${TEAL}${BOLD}🔄 Press R to restart  ·  Q to quit${RESET}"
        echo ""
        echo -n "  > "
        read -r -n1 choice
        echo ""
        case "$choice" in
            r|R)
                echo ""
                echo -e "  ${META_BLUE}${BOLD}♻️  Restarting Web App Creator...${RESET}"
                echo ""
                sleep 1
                exec "$0"
                ;;
            q|Q|"")
                echo ""
                echo -e "  ${TXT_BODY}👋 Goodbye!${RESET}"
                echo ""
                exit 0
                ;;
            *)
                echo -e "  ${TXT_CAP}  (r = restart, q = quit)${RESET}"
                ;;
        esac
    done
}
trap cleanup SIGINT SIGTERM SIGHUP

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Streaming profile selection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROFILE_LIGHT="$PROJECT_DIR/profiles/web_app_creator_light.json"

# Default: mp_streaming_demo (built-in SDK profile, full streams)
PROFILE_MODE="builtin"
PROFILE_NAME="mp_streaming_demo"
PROFILE_DESC="Full streams (built-in SDK profile)"

# Check WEB_APP_CREATOR_PROFILE env var override
if [ -n "${WEB_APP_CREATOR_PROFILE:-}" ]; then
    case "$WEB_APP_CREATOR_PROFILE" in
        mp_streaming_demo)
            PROFILE_MODE="builtin"
            PROFILE_NAME="mp_streaming_demo"
            PROFILE_DESC="Full streams (built-in SDK profile)"
            log "${OK}✔ Profile override: mp_streaming_demo (via WEB_APP_CREATOR_PROFILE env var)${RESET}"
            ;;
        web_app_creator_light|light)
            log "${OK}✔ Profile override: web_app_creator_light (via WEB_APP_CREATOR_PROFILE env var)${RESET}"
            ;;
        *)
            PROFILE_MODE="builtin"
            PROFILE_NAME="$WEB_APP_CREATOR_PROFILE"
            PROFILE_DESC="Custom profile"
            log "${WARN}⚠ Custom WEB_APP_CREATOR_PROFILE='$WEB_APP_CREATOR_PROFILE'${RESET}"
            ;;
    esac
else
    # Interactive profile selection prompt
    echo -e "  ${TEAL}${BOLD}⚡ Streaming Profile${RESET}"
    echo ""
    echo -e "    ${OK}${BOLD}[1]${RESET} ${TXT}mp_streaming_demo${RESET}  ${TXT_CAP}Standard SDK profile, full streams${RESET}   ${OK}— recommended ✓${RESET}"
    echo -e "    ${TXT_LABEL}${BOLD}[2]${RESET} ${TXT}web_app_creator_light${RESET}     ${TXT_CAP}VIO, hands, gaze, audio, RGB (low-latency)${RESET}"
    echo ""
    echo -ne "    ${TXT_CAP}Press 1 or 2 (default: 1, auto-selects in 5s): ${RESET}"

    PROFILE_CHOICE=""
    read -r -t 5 -n 1 PROFILE_CHOICE || true
    echo ""

    case "$PROFILE_CHOICE" in
        2)
            PROFILE_MODE="json"
            PROFILE_JSON="$PROFILE_LIGHT"
            PROFILE_NAME="web_app_creator_light"
            PROFILE_DESC="VIO, hands, gaze, audio, RGB, PPG (low-latency)"
            log "${TXT}  → web_app_creator_light selected${RESET}"
            ;;
        *)
            log "${OK}  → mp_streaming_demo selected${RESET}"
            ;;
    esac
fi
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 1/2: Aria device streaming (MUST start before WebSocket bridge)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# aria_gen2 streaming start must run FIRST because it generates/updates
# TLS certs at ~/.aria/streaming-certs/. If the WebSocket bridge's
# StreamReceiver starts first, it races with cert file writes and
# the C++ TLS layer crashes with "couldn't read cert file" (libc++abi terminate).

RETRY_INTERVAL=10
RETRY_COUNT=0

echo -e "  ${META_BLUE}${BOLD}[6/7]${RESET} ${TXT}Aria device streaming ${TXT_CAP}(profile: ${PROFILE_NAME})${RESET}"
log_file "[6/7] Aria device streaming — profile: $PROFILE_NAME"

if [ -x "$ARIA_CLI" ]; then
    # ── Pre-flight: device discovery (catches mDNS / hostile-network failures BEFORE auth pair) ──
    step_start "${TXT_CAP}  Pre-flight: discovering Aria glasses on local network...${RESET}"
    discover_output=$("$ARIA_CLI" device list 2>&1)
    discover_exit=$?
    log_file "device list exit code: $discover_exit"
    log_file "device list output: $discover_output"

    # End-to-end toolchain check: a successful discovery emits an Aria device
    # serial (e.g. "1M0YDD6H8C0173" — 14+ uppercase alphanumeric chars). If the
    # output contains no such serial, treat as failure even if exit code is 0
    # — this is what the v2.7.7 silent-aria_gen2 bug looked like.
    discover_failed=false
    if [ $discover_exit -ne 0 ]; then
        discover_failed=true
    elif echo "$discover_output" | grep -qiE "mDNS|port 5353|no device|not found|0 device|empty"; then
        discover_failed=true
    elif ! echo "$discover_output" | grep -qE "[0-9A-Z]{12,}"; then
        # Vacuous success — exit 0 but no serial in output. Check adb directly.
        log_file "Vacuous-success discovery (exit 0, no serial in output). Checking adb state..."
        adb_out=$(adb devices 2>&1 || echo 'adb not callable')
        log_file "adb devices output: $adb_out"
        if echo "$adb_out" | grep -qE "[0-9A-Z]{12,}[[:space:]]+device"; then
            # adb sees an authorized device — aria_gen2 device list is just silent, not broken
            log_file "adb confirms device connected — treating as discovered"
        else
            discover_failed=true
        fi
    fi

    if $discover_failed; then
        log "${ERR}  ✖ Could not discover Aria glasses${RESET}"
        log_file "FAIL: device discovery failed — likely mDNS blocked or USB Networking not enabled"
        echo ""
        echo -e "  ${WARN}${BOLD}🌐 Network discovery failed${RESET}"
        echo ""
        echo -e "  ${LIGHT}    This usually means one of two things:${RESET}"
        echo -e "  ${LIGHT}      ${BOLD}A.${RESET}${LIGHT} You're on a corporate / guest Wi-Fi (e.g. Meta Guest, conference Wi-Fi)"
        echo -e "  ${LIGHT}         that blocks mDNS/Bonjour (UDP port 5353).${RESET}"
        echo -e "  ${LIGHT}      ${BOLD}B.${RESET}${LIGHT} USB Networking is not enabled in the Aria Companion App.${RESET}"
        echo ""
        echo -e "  ${LIGHT}${BOLD}Fix (recommended):${RESET}"
        echo -e "  ${LIGHT}    1. Connect the glasses to this Mac via the supplied ${BOLD}USB-C cable${RESET}"
        echo -e "  ${LIGHT}    2. Open the ${BOLD}Aria Companion App${RESET}${LIGHT} on your phone"
        echo -e "  ${LIGHT}    3. Settings → Glasses → ${BOLD}Enable USB Networking${RESET}"
        echo -e "  ${LIGHT}    4. Re-run this launcher${RESET}"
        echo ""
        echo -e "  ${LIGHT}If you're on home Wi-Fi and USB Networking is already enabled,${RESET}"
        echo -e "  ${LIGHT}check that the glasses are powered on and not asleep.${RESET}"
        echo ""
        echo "Press any key to close..."; read -n1; exit 1
    else
        step_done "${OK}✔ Aria glasses discovered${RESET}"
    fi

    # ── Ensure device is auth-paired (required before install-certs can generate certs) ──
    CERT_DIR="$HOME/.aria/streaming-certs"
    TLS_DIR="$HOME/.aria/tls-client-certs"

    # Snapshot ~/.aria/ state for remote debugging
    log_file "── ~/.aria/ state before auth/cert steps ──"
    log_file "$(ls -laR "$HOME/.aria/" 2>&1 || echo '~/.aria/ does not exist')"
    log_file "── end ~/.aria/ snapshot ──"

    step_start "${TXT_CAP}  Checking device auth pairing...${RESET}"
    auth_output=$("$ARIA_CLI" auth check 2>&1)
    auth_exit=$?
    log_file "auth check exit code: $auth_exit"
    log_file "auth check output: $auth_output"

    # Count actual TLS client cert files (.pem / .p12) — the per-serial subfolder
    # is what really matters; the parent dir alone is not enough. After a wipe
    # of ~/.aria/ the SDK may recreate the parent dir + an empty subfolder for
    # the freshly-discovered serial without doing the actual pairing handshake,
    # and `auth check` may exit 0 with no output (vacuous success). Falling
    # through to streaming in that state produces SDK error 980
    # ("not paired with the device") on every poll. So require >=1 real cert
    # file under TLS_DIR before we trust the "paired" state.
    tls_cert_count=0
    if [ -d "$TLS_DIR" ]; then
        tls_cert_count=$(find "$TLS_DIR" -type f \( -name "*.pem" -o -name "*.p12" \) 2>/dev/null | wc -l | tr -d ' ')
    fi
    log_file "TLS cert file count under $TLS_DIR: $tls_cert_count"

    if echo "$auth_output" | grep -qi "not authenticated\|not paired\|no device\|error\|failed" \
       || [ ! -d "$TLS_DIR" ] \
       || [ "$tls_cert_count" -eq 0 ]; then
        log "${WARN}  ⚠ Device not auth-paired with this computer${RESET}"
        log_file "WARN: Device not auth-paired — initiating auth pair"
        echo ""
        echo -e "  ${TEAL}${BOLD}🔐 First-time setup: Device pairing required${RESET}"
        echo ""
        echo -e "  ${TXT_CAP}    This is a one-time step. Your Aria glasses need to be paired${RESET}"
        echo -e "  ${TXT_CAP}    with this computer before streaming certificates can be generated.${RESET}"
        echo ""
        echo -e "  ${WARN}${BOLD}📱 Please have the Aria Companion App open on your phone.${RESET}"
        echo -e "  ${TXT_CAP}    You will need to approve the pairing request there.${RESET}"
        echo ""

        step_start "${TXT_CAP}  Running auth pair (waiting for approval in Companion App)...${RESET}"
        # Capture pre-pair TLS dir state to detect silent-success (exit 0 but no new artifacts written)
        pair_t0=$(date +%s)
        pair_output=$("$ARIA_CLI" auth pair 2>&1)
        pair_exit=$?
        log_file "auth pair exit code: $pair_exit"
        log_file "auth pair output: $pair_output"

        # Silent-success guard: exit 0 means little if no new credential file was actually written.
        # Look for any file under TLS_DIR modified in the last 90 seconds.
        pair_artifact_found=false
        if [ -d "$TLS_DIR" ]; then
            # find -newermt is BSD-incompatible; use mmin instead (90s = 1.5 min)
            if [ -n "$(find "$TLS_DIR" -type f -mmin -2 2>/dev/null | head -1)" ]; then
                pair_artifact_found=true
            fi
        fi

        if [ $pair_exit -eq 0 ] && ! echo "$pair_output" | grep -qi "error\|failed\|denied" && $pair_artifact_found; then
            step_done "${OK}✔ Device auth pairing successful${RESET}"
            log_file "OK: auth pair succeeded — fresh artifacts in $TLS_DIR"
        elif [ $pair_exit -eq 0 ] && ! $pair_artifact_found; then
            log "${ERR}  ✖ Auth pair returned success but no new credentials were written${RESET}"
            log "${TXT_CAP}    This usually means the pairing was not approved on the phone.${RESET}"
            log_file "FAIL: auth pair silent-success — exit 0 but no fresh files in $TLS_DIR"
            log_file "TLS dir contents: $(ls -la "$TLS_DIR/" 2>&1 || echo 'directory missing')"
            echo ""
            echo -e "  ${ERR}${BOLD}🔐 Pairing approval not received${RESET}"
            echo ""
            echo -e "  ${TXT_CAP}    Make sure:${RESET}"
            echo -e "  ${TXT_CAP}      • You ${BOLD}approved${RESET}${TXT_CAP} the pairing prompt in the Aria Companion App${RESET}"
            echo -e "  ${TXT_CAP}      • The Companion App is signed into the ${BOLD}correct account${RESET}"
            echo -e "  ${TXT_CAP}      • The Companion App on the phone is already paired with these glasses${RESET}"
            echo -e "  ${TXT_CAP}        (it must show this device serial in its device list)${RESET}"
            echo ""
            echo -e "  ${TXT_CAP}    Re-run this launcher when ready.${RESET}"
            log_file "FAIL: exiting because pairing approval is required before any streaming can work"
            echo ""; echo "Press any key to close..."; read -n1; exit 1
        else
            log "${ERR}  ✖ Auth pairing failed${RESET}"
            log_file "FAIL: auth pair failed — $pair_output"
            log_file "~/.aria/ state after failed auth pair: $(ls -laR "$HOME/.aria/" 2>&1 || echo 'does not exist')"
            echo ""
            echo -e "  ${ERR}${BOLD}🔐 Pairing failed${RESET}"
            echo ""
            echo -e "  ${TXT_CAP}    Make sure:${RESET}"
            echo -e "  ${TXT_CAP}      • Glasses are ${BOLD}switched ON${RESET}${TXT_CAP} and connected via ${BOLD}USB${RESET}"
            echo -e "  ${TXT_CAP}      • You ${BOLD}approved the request${RESET}${TXT_CAP} in the Aria Companion App${RESET}"
            echo -e "  ${TXT_CAP}      • The Companion App is signed into the correct account${RESET}"
            echo ""
            log_file "FAIL: exiting because pairing is required before any streaming can work"
            echo ""; echo "Press any key to close..."; read -n1; exit 1
        fi
        echo ""
    else
        step_done "${OK}✔ Device auth paired${RESET}"
        log_file "OK: auth check passed — output: $auth_output"
        log_file "TLS client certs: $(ls -la "$TLS_DIR/" 2>&1 || echo 'directory missing')"
    fi

    # ── Streaming certificate strategy ──
    # Per the official ARK docs (https://facebookresearch.github.io/projectaria_tools/gen2/ark/client-sdk/streaming),
    # the public flow is just `aria_gen2 streaming start` after `auth pair` — no manual
    # `install-certs` step is required. But the WebSocket bridge's StreamReceiver
    # (websocket_bridge.py) loads certs from ~/.aria/streaming-certs/{persistent,ephemeral}/
    # at TLS-server construction time, and BOTH sides (device-side publisher and
    # host-side subscriber/bridge) must use the SAME cert set or TLS handshake
    # silently fails and frames are dropped.
    #
    # Strategy:
    #   1. Warm-up install-certs (best-effort). If it succeeds, persistent/ is
    #      populated and the bridge will prefer it.
    #   2. If persistent certs exist after warm-up → device uses persistent too
    #      (no --use-ephemeral-certs). Match!
    #   3. If persistent certs do NOT exist → pass --use-ephemeral-certs AND wipe
    #      stale persistent files so the bridge falls back to ephemeral. Match!
    step_start "${TXT_CAP}  Warming up streaming certificates (best-effort)...${RESET}"
    cert_output=$("$ARIA_CLI" streaming install-certs 2>&1)
    cert_exit=$?
    log_file "install-certs exit code: $cert_exit"
    log_file "install-certs output: $cert_output"

    CERT_FLAG=""  # default: device uses persistent certs (matches bridge default)
    if [ -f "$CERT_DIR/persistent/root_ca.pem" ]; then
        step_done "${OK}✔ Persistent streaming certs available — device + bridge will both use persistent${RESET}"
        log_file "Persistent certs: $(ls -la "$CERT_DIR/persistent/" 2>&1)"
    else
        step_done "${WARN}⚠ No persistent certs — falling back to ephemeral certs (both sides)${RESET}"
        log_file "INFO: install-certs did not produce persistent certs. Using --use-ephemeral-certs and removing stale persistent/ so bridge falls back to ephemeral/."
        CERT_FLAG="--use-ephemeral-certs"
        # Wipe stale persistent dir so bridge does NOT preferentially load it.
        # (websocket_bridge.py:2304 prefers persistent over ephemeral.)
        if [ -d "$CERT_DIR/persistent" ]; then
            rm -rf "$CERT_DIR/persistent"
            log_file "Removed stale $CERT_DIR/persistent so bridge falls back to ephemeral certs"
        fi
    fi

    while true; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        step_start "${TXT_CAP}  Attempting to connect to Aria glasses (attempt #$RETRY_COUNT)...${RESET}"

        if [ "$PROFILE_MODE" = "json" ]; then
            output=$("$ARIA_CLI" streaming start --interface usb $CERT_FLAG --json-profile "$PROFILE_JSON" 2>&1)
        else
            output=$("$ARIA_CLI" streaming start --interface usb $CERT_FLAG --profile "$PROFILE_NAME" 2>&1)
        fi

        if echo "$output" | grep -qi "Unable to connect\|No device\|not found\|error\|failed"; then
            log "${ERR}  ✖ No Aria glasses detected${RESET}"
            log_file "FAIL attempt #$RETRY_COUNT: $output"
            echo ""
            echo -e "  ${WARN}${BOLD}📱 Waiting for Aria glasses connection...${RESET}"
            echo -e "  ${TXT_CAP}    • Make sure glasses are ${BOLD}switched ON${RESET}"
            echo -e "  ${TXT_CAP}    • Connect via ${BOLD}USB cable${RESET}"
            echo -e "  ${TXT_CAP}    • Approve pairing in Aria Companion App (if first time)${RESET}"
            echo ""

            for ((i=RETRY_INTERVAL; i>0; i--)); do
                echo -ne "  ${TXT_CAP}Retrying in ${TEAL}${BOLD}${i}s${RESET}${TXT_CAP}... (${ERR}Ctrl+C${TXT_CAP} to exit)${RESET}  \r"
                sleep 1
            done
            echo -e "  ${TXT_CAP}Retrying now...                              ${RESET}"
            echo ""
        else
            log "${OK}  ✔ Aria streaming started (attempt #$RETRY_COUNT)${RESET}"
            log_file "OK: aria_gen2 streaming started — $output"
            break
        fi
    done

    # ── 🚨 USB-streaming + glasses-Wi-Fi black hole detection ──
    # After USB streaming is started, the glasses' Wi-Fi radio should be off (or at least
    # not on a hostile network). If glasses are on Meta Guest / corp Wi-Fi (CGNAT 100.x.x.x),
    # the USB transport gets black-holed and the host sees zero bytes — the LED stays off.
    step_start "${TXT_CAP}  Checking glasses Wi-Fi state (USB streaming sanity)...${RESET}"
    status_output=$("$ARIA_CLI" device status 2>&1)
    log_file "device status output: $status_output"

    wifi_connected=$(echo "$status_output" | grep -iE "Wi-?Fi (connected|status)" | head -1)
    wifi_ip=$(echo "$status_output" | grep -iE "Wi-?Fi IP( address)?" | head -1 | awk -F'[: ]+' '{print $NF}')
    wifi_ssid=$(echo "$status_output" | grep -iE "Wi-?Fi SSID|SSID" | head -1 | awk -F'[:]+' '{print $NF}' | sed 's/^ *//')

    glasses_on_wifi=false
    cgnat=false
    if echo "$wifi_connected" | grep -qiE "true|yes|connected"; then
        glasses_on_wifi=true
    elif [ -n "$wifi_ip" ] && echo "$wifi_ip" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
        glasses_on_wifi=true
    fi

    if [ -n "$wifi_ip" ] && echo "$wifi_ip" | grep -qE '^100\.[0-9]+\.[0-9]+\.[0-9]+$'; then
        cgnat=true
    fi

    if $cgnat; then
        log "${ERR}  ✖ Glasses are on a CGNAT network (IP: $wifi_ip${wifi_ssid:+, SSID: $wifi_ssid})${RESET}"
        log_file "ERROR: CGNAT IP detected on glasses Wi-Fi — USB streaming will be black-holed"
        echo ""
        echo -e "  ${ERR}${BOLD}🚫 Hostile glasses Wi-Fi detected${RESET}"
        echo -e "  ${TXT_CAP}    The glasses are connected to a guest/captive network (Meta Guest, corp guest, etc.)."
        echo -e "  ${TXT_CAP}    USB streaming WILL be black-holed in this state — no data reaches the host.${RESET}"
        echo ""
        echo -ne "  ${TEAL}${BOLD}Disable glasses Wi-Fi now? [Y/n]: ${RESET}"
        read -r WIFI_FIX_CHOICE
        case "${WIFI_FIX_CHOICE:-Y}" in
            n|N)
                log "${WARN}  ⚠ User declined to disable glasses Wi-Fi — streaming will likely show no data${RESET}"
                log_file "WARN: User declined Wi-Fi disable"
                ;;
            *)
                step_start "${TXT_CAP}  Disabling glasses Wi-Fi...${RESET}"
                wifi_off_output=""
                wifi_off_ok=false
                for sub in off disable disconnect; do
                    wifi_off_output=$("$ARIA_CLI" device wifi $sub 2>&1)
                    wifi_off_exit=$?
                    log_file "device wifi $sub exit=$wifi_off_exit output=$wifi_off_output"
                    if [ $wifi_off_exit -eq 0 ] && ! echo "$wifi_off_output" | grep -qiE "unknown|invalid|usage|no such"; then
                        wifi_off_ok=true
                        break
                    fi
                done
                if $wifi_off_ok; then
                    step_done "${OK}✔ Glasses Wi-Fi disabled${RESET}"
                else
                    log "${WARN}  ⚠ Could not auto-disable glasses Wi-Fi via aria_gen2 CLI${RESET}"
                    echo -e "  ${TXT_CAP}    Manually toggle Wi-Fi off on the glasses via the Companion App,${RESET}"
                    echo -e "  ${TXT_CAP}    then re-run this launcher.${RESET}"
                fi
                ;;
        esac
    elif $glasses_on_wifi; then
        log "${WARN}  ⚠ Glasses are on Wi-Fi (IP: ${wifi_ip:-unknown}${wifi_ssid:+, SSID: $wifi_ssid}) while USB streaming was requested${RESET}"
        log_file "WARN: glasses on Wi-Fi during USB streaming"
        echo ""
        echo -e "  ${WARN}    USB streaming may behave unpredictably while glasses Wi-Fi is on.${RESET}"
        echo -ne "  ${TEAL}${BOLD}Disable glasses Wi-Fi now? [Y/n]: ${RESET}"
        read -r WIFI_FIX_CHOICE
        case "${WIFI_FIX_CHOICE:-Y}" in
            n|N)
                log_file "User declined Wi-Fi disable (non-CGNAT case)"
                ;;
            *)
                wifi_off_ok=false
                for sub in off disable disconnect; do
                    wifi_off_output=$("$ARIA_CLI" device wifi $sub 2>&1)
                    wifi_off_exit=$?
                    log_file "device wifi $sub exit=$wifi_off_exit output=$wifi_off_output"
                    if [ $wifi_off_exit -eq 0 ] && ! echo "$wifi_off_output" | grep -qiE "unknown|invalid|usage|no such"; then
                        wifi_off_ok=true
                        break
                    fi
                done
                if $wifi_off_ok; then
                    log "${OK}  ✔ Glasses Wi-Fi disabled${RESET}"
                fi
                ;;
        esac
    else
        step_done "${OK}✔ Glasses Wi-Fi clean (USB-only)${RESET}"
    fi
else
    log "${WARN}  ⚠ aria_gen2 CLI not found in venv${RESET}"
    log_file "WARN: aria_gen2 not found at $ARIA_CLI"
    echo -e "  ${TXT_CAP}    Run: pip install projectaria-client-sdk${RESET}"
fi
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 2/2: WebSocket Streaming Server (starts after certs are stable)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# StreamReceiver loads TLS certs from ~/.aria/streaming-certs/ at startup.
# Starting after aria_gen2 ensures certs exist and are not being rewritten.

echo -e "  ${META_BLUE}${BOLD}[7/7]${RESET} ${TXT}WebSocket Server ${TXT_CAP}(port 17300 / 6768)${RESET}"
step_start "${TXT_CAP}  Launching WebSocket bridge...${RESET}"
"$PROJECT_DIR/venv/bin/python3" -m backend.websocket_bridge > "$WS_LOG" 2>&1 &
WEBSOCKET_PID=$!
sleep 3

if ps -p $WEBSOCKET_PID > /dev/null 2>&1; then
    # Double-check: even if PID is alive, verify no Python-level crash in the log.
    # IMPORTANT: Only flag genuine Python exceptions / fatal errors.
    # Ignore noisy native-lib decoder logs that happen normally at stream start, e.g.:
    #   [hevc @ 0x...] PPS id out of range
    #   [hevc @ 0x...] Skipping invalid undecodable NALU
    #   [XPRS][ERROR]: Error at FFmpegDecode.cpp:104: End of file
    # These come from FFmpeg/XPRS recovering when packets arrive mid-GOP; the
    # bridge process is fine and starts producing frames a moment later.
    PY_CRASH_RE='Traceback \(most recent call last\)|^[A-Za-z_]*Error:|^[A-Za-z_]*Exception:|RuntimeError|fatal error|FATAL'
    if grep -E "$PY_CRASH_RE" "$WS_LOG" 2>/dev/null | grep -vE '^\[hevc |^\[XPRS\]|FFmpegDecode\.cpp' | head -1 | grep -q . ; then
        WS_ERROR=$(grep -E "$PY_CRASH_RE" "$WS_LOG" 2>/dev/null | grep -vE '^\[hevc |^\[XPRS\]|FFmpegDecode\.cpp' | head -1)
        log "${ERR}  ✖ WebSocket Server crashed: ${WS_ERROR}${RESET}"
        log_file "FAIL: WebSocket log contains Python-level error: $WS_ERROR"
        echo -e "  ${TXT_CAP}    See full log: ${LINK}$WS_LOG${RESET}"
    else
        step_done "${OK}  ✔ WebSocket Server running (PID $WEBSOCKET_PID)${RESET}"
        log_file "OK: WebSocket server PID=$WEBSOCKET_PID alive after 3s"
    fi
else
    # Process died — extract the error from the log (apply same filter)
    PY_CRASH_RE='Traceback \(most recent call last\)|^[A-Za-z_]*Error:|^[A-Za-z_]*Exception:|RuntimeError|fatal error|FATAL'
    WS_ERROR=$(grep -E "$PY_CRASH_RE" "$WS_LOG" 2>/dev/null | grep -vE '^\[hevc |^\[XPRS\]|FFmpegDecode\.cpp' | head -1)
    if [ -n "$WS_ERROR" ]; then
        log "${ERR}  ✖ WebSocket Server crashed: ${WS_ERROR}${RESET}"
        log_file "FAIL: WebSocket server PID=$WEBSOCKET_PID died — $WS_ERROR"
    else
        log "${WARN}  ⚠ WebSocket Server may have failed ${TXT_CAP}(see $WS_LOG)${RESET}"
        log_file "WARN: WebSocket server PID=$WEBSOCKET_PID died within 3s"
    fi
    echo -e "  ${TXT_CAP}    See full log: ${LINK}$WS_LOG${RESET}"
fi
echo ""

# ── Post-start watchdog: check for data flow within 10s of WebSocket bridge launch ──
# If aria_websocket.log shows Total:0 after 10s, surface a loud diagnostic
# rather than letting the user assume the launcher is hung.
if [ -n "$WEBSOCKET_PID" ] && ps -p $WEBSOCKET_PID > /dev/null 2>&1; then
    step_start "${TXT_CAP}  Watching for data flow (10s)...${RESET}"
    sleep 10
    # Look at last 20 lines for any Stats line with Total:N where N > 0
    recent_stats=$(tail -n 20 "$WS_LOG" 2>/dev/null | grep -E "Stats:.*Total:[0-9]+" | tail -1)
    if [ -n "$recent_stats" ]; then
        if echo "$recent_stats" | grep -qE "Total:0\b"; then
            log "${ERR}  ✖ WebSocket bridge is up but no data is flowing (Total:0 after 10s)${RESET}"
            log_file "WATCHDOG FAIL: $recent_stats"
            echo ""
            echo -e "  ${ERR}${BOLD}🚫 Streaming silent — no sensor data is reaching the bridge${RESET}"
            echo -e "  ${TXT_CAP}    The WebSocket bridge is running and the glasses claim USB streaming started,${RESET}"
            echo -e "  ${TXT_CAP}    but no sensor frames are arriving. Common causes:${RESET}"
            echo -e "  ${TXT_CAP}      • Glasses Wi-Fi is on a hostile network (see prompt above)${RESET}"
            echo -e "  ${TXT_CAP}      • USB Networking is not enabled in Aria Companion App${RESET}"
            echo -e "  ${TXT_CAP}      • USB cable is data-poor (charge-only) — try a different cable${RESET}"
            echo ""
            echo -e "  ${TXT_CAP}See: ${LINK}$WS_LOG${RESET}"
            echo ""
            # Fail-fast: a bridge with no data is worse than no bridge at all.
            # Recipients ended up debugging a green-banner-but-no-frames UI for
            # half an hour in v2.7.7 — don't let that happen again.
            log_file "FAIL: exiting because streaming watchdog saw zero frames after 10s"
            echo "Press any key to close..."; read -n1; exit 1
        else
            step_done "${OK}✔ Data flowing — $recent_stats${RESET}"
            log_file "WATCHDOG OK: $recent_stats"
        fi
    else
        log "${WARN}  ⚠ No Stats lines in WebSocket log yet — bridge may still be warming up${RESET}"
        log_file "WATCHDOG: no Stats lines after 10s in $WS_LOG"
    fi
    echo ""
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Status summary (bg: Dark Teal #0C292F)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo -e "${BG_DARK}${EOL}${RESET}"
echo -e "${BG_DARK}   ${TEAL}${BOLD}🎉  WEB APP CREATOR BACKEND SERVICE READY${RESET}${BG_DARK}${EOL}${RESET}"
echo -e "${BG_DARK}   ${LIGHT}Leave this terminal as it is and start creating by chatting with the agent.${RESET}${BG_DARK}${EOL}${RESET}"
echo -e "${BG_DARK}${EOL}${RESET}"
echo -e "${BG_DARK}   ${WHITE}${BOLD}SERVICES${RESET}${BG_DARK}${EOL}${RESET}"
echo -e "${BG_DARK}   ${META_BLUE}▸${RESET}${BG_DARK} ${LIGHT}Aria Streaming${RESET}${BG_DARK}      ${LIGHT}profile ${PROFILE_NAME} — ${PROFILE_DESC}${RESET}${BG_DARK}${EOL}${RESET}"
echo -e "${BG_DARK}   ${META_BLUE}▸${RESET}${BG_DARK} ${LIGHT}WebSocket${RESET}${BG_DARK}           ${LIGHT}ws://localhost:17300${RESET}${BG_DARK}${EOL}${RESET}"

# ── Auto-derive paths to the two bundled HTML demos ───────────────────────────
# Templates live in the sibling templates/ folder; the .command file is at
# skills/web-app-creator/web-app-creator-backend/, so templates/ is one level up.
TEMPLATES_DIR_ABS="$(cd "$PROJECT_DIR/../templates" 2>/dev/null && pwd || echo "")"
DEVICE_POSE_HTML=""
STREAM_PANEL_HTML=""
if [ -n "$TEMPLATES_DIR_ABS" ]; then
    DEVICE_POSE_HTML="$TEMPLATES_DIR_ABS/device-pose-and-hands/DevicePoseAndHands.html"
    STREAM_PANEL_HTML="$TEMPLATES_DIR_ABS/stream-panels/StreamPanel.html"
fi

if { [ -n "$DEVICE_POSE_HTML" ] && [ -f "$DEVICE_POSE_HTML" ]; } || \
   { [ -n "$STREAM_PANEL_HTML" ] && [ -f "$STREAM_PANEL_HTML" ]; }; then
    echo -e "${BG_DARK}${EOL}${RESET}"
    echo -e "${BG_DARK}   ${WHITE}${BOLD}DEMO HTMLS${RESET}${BG_DARK}${EOL}${RESET}"
    if [ -n "$DEVICE_POSE_HTML" ] && [ -f "$DEVICE_POSE_HTML" ]; then
        echo -e "${BG_DARK}   ${TEAL}▸${RESET}${BG_DARK} ${LIGHT}DevicePoseAndHands${RESET}${BG_DARK}  ${LINK}file://${DEVICE_POSE_HTML}${RESET}${BG_DARK}${EOL}${RESET}"
    fi
    if [ -n "$STREAM_PANEL_HTML" ] && [ -f "$STREAM_PANEL_HTML" ]; then
        echo -e "${BG_DARK}   ${TEAL}▸${RESET}${BG_DARK} ${LIGHT}StreamPanel${RESET}${BG_DARK}         ${LINK}file://${STREAM_PANEL_HTML}${RESET}${BG_DARK}${EOL}${RESET}"
    fi
fi
echo -e "${BG_DARK}${EOL}${RESET}"
echo -e "${BG_DARK}   ${ERR}${BOLD}🛑 Ctrl+C${RESET}${BG_DARK}${LIGHT} or close window to stop all services${RESET}${BG_DARK}${EOL}${RESET}"
echo -e "${BG_DARK}${EOL}${RESET}"
echo ""

# ── Auto-open the primary stream panel HTML in the default browser ───────────────
# The user can still open DevicePoseAndHands.html manually via the DEMO HTMLS link above.
if [ -n "$STREAM_PANEL_HTML" ] && [ -f "$STREAM_PANEL_HTML" ]; then
    open "$STREAM_PANEL_HTML" 2>/dev/null && \
        log_file "Auto-opened StreamPanel.html in default browser"
fi

log_file "════════════════════════════════════════════════"
log_file "  Startup complete — entering keep-alive loop"
log_file "════════════════════════════════════════════════"

# Keep alive — Ctrl+C or closing window triggers cleanup
while true; do sleep 60; done
