#!/usr/bin/env bash
# ============================================================
#  IT Ticketing System  |  v1.0
#  macOS / Linux Setup Script
#
#  Usage:
#    chmod +x setup.sh   (one time only)
#    ./setup.sh
#
#  Starts the server in the BACKGROUND — safe to close the
#  terminal after it launches.
#  To stop: ./stop_server.sh  OR  kill $(cat logs/server.pid)
# ============================================================

set -e

# Colours
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}  OK: $*${RESET}"; }
err()  { echo -e "${RED}  ERROR: $*${RESET}"; }
info() { echo -e "${CYAN}  $*${RESET}"; }
warn() { echo -e "${YELLOW}  WARN: $*${RESET}"; }

echo ""
echo "  ============================================================"
echo "    IT Ticketing System  |  v1.0"
echo "    macOS / Linux Setup"
echo "  ============================================================"
echo ""

# ── 1. Locate script root ────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$SCRIPT_DIR/backend"
LOGS="$SCRIPT_DIR/logs"

if [ ! -f "$BACKEND/main.py" ]; then
    err "backend/main.py not found."
    echo "  Make sure setup.sh is in the project root folder."
    exit 1
fi

mkdir -p "$LOGS"

# ── 2. Python check ──────────────────────────────────────
echo "  [1/5] Checking Python..."
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    err "Python 3 not found."
    echo "  macOS : brew install python3"
    echo "  Ubuntu: sudo apt install python3 python3-pip"
    exit 1
fi
ok "$($PYTHON --version)"

# ── 3. Install dependencies ──────────────────────────────
echo ""
echo "  [2/5] Installing dependencies..."
cd "$BACKEND"
$PYTHON -m pip install --upgrade pip --quiet 2>/dev/null || true
$PYTHON -m pip install -r requirements.txt --quiet
ok "Dependencies installed."

# ── 4. Detect server IP ──────────────────────────────────
echo ""
echo "  [3/5] Detecting server IP..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    LAN_IP=$(ipconfig getifaddr en0 2>/dev/null \
          || ipconfig getifaddr en1 2>/dev/null \
          || echo "127.0.0.1")
else
    LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
fi
ok "IP: $LAN_IP"

# ── 5. Stop any existing server ──────────────────────────
echo ""
echo "  [4/5] Stopping any running server on port 8000..."
PID_FILE="$LOGS/server.pid"
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$PID_FILE"
fi
# Also kill anything on port 8000
if command -v lsof &>/dev/null; then
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
fi
ok "Done."

# ── 6. Launch server in background ───────────────────────
echo ""
echo "  [5/5] Starting server in background..."
LOG_FILE="$LOGS/server.log"

cd "$BACKEND"
nohup $PYTHON -m uvicorn main:app \
    --host 0.0.0.0 --port 8000 \
    >> "$LOG_FILE" 2>&1 &

SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

# Brief wait so uvicorn has time to bind
sleep 2

# Verify it started
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    err "Server failed to start. Check logs:"
    echo "    cat $LOG_FILE"
    exit 1
fi
ok "Server running (PID $SERVER_PID)"

# ── Write stop_server.sh ─────────────────────────────────
cat > "$SCRIPT_DIR/stop_server.sh" << 'STOPEOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/logs/server.pid"
echo "Stopping IT Ticketing System server..."
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    kill "$PID" 2>/dev/null && echo "  Stopped PID $PID." || echo "  Process not running."
    rm -f "$PID_FILE"
fi
if command -v lsof &>/dev/null; then
    lsof -ti :8000 | xargs kill -9 2>/dev/null && echo "  Cleared port 8000." || true
fi
echo "Done."
STOPEOF
chmod +x "$SCRIPT_DIR/stop_server.sh"

# ── Print access info ─────────────────────────────────────
echo ""
echo "  ============================================================"
echo "    Server running in BACKGROUND"
echo "    Safe to close this terminal — server keeps running."
echo ""
echo "    Admin Panel  |  http://$LAN_IP:8000/admin"
echo "    Tech Panel   |  http://$LAN_IP:8000/tech"
echo "    Health Check |  http://$LAN_IP:8000/health"
echo ""
echo "    Default login:  admin / admin123"
echo "    Change password on first login!"
echo ""
echo "    Client config:  SERVER_URL = \"http://$LAN_IP:8000\""
echo ""
echo "    Logs:           logs/server.log"
echo "    Stop server:    ./stop_server.sh"
echo "    Restart server: ./setup.sh again"
echo "  ============================================================"
echo ""
