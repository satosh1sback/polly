#!/usr/bin/env bash
# ─────────────────────────────────────────────
#  Pulse — local dev startup script
#  Run this from the project root OR from
#  inside artifacts/api-server-python/
# ─────────────────────────────────────────────

set -e

# Work out where the Python app lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR"

# If run from project root, step into the app folder
if [ -f "$APP_DIR/artifacts/api-server-python/run.py" ]; then
  APP_DIR="$APP_DIR/artifacts/api-server-python"
fi

echo ""
echo "==============================="
echo "  Pulse — Local Setup"
echo "==============================="
echo ""

# ── Check Python ──────────────────────────────
PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    VER=$("$cmd" -c "import sys; print(sys.version_info >= (3,11))" 2>/dev/null)
    if [ "$VER" = "True" ]; then
      PYTHON="$cmd"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "ERROR: Python 3.11+ is required but was not found."
  echo "       Download it from https://www.python.org/downloads/"
  exit 1
fi

echo "Python found: $($PYTHON --version)"

# ── Check DATABASE_URL ────────────────────────
if [ -z "$DATABASE_URL" ]; then
  echo ""
  echo "DATABASE_URL is not set."
  echo "Paste your Replit DATABASE_URL secret (or a local PostgreSQL URL) below."
  echo "Example format: postgresql://user:password@host:5432/dbname"
  echo ""
  read -rp "DATABASE_URL: " DATABASE_URL
  if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL cannot be empty."
    exit 1
  fi
  export DATABASE_URL
fi

echo "Database: connected (URL is set)"

# ── Install dependencies ──────────────────────
echo ""
echo "Installing Python packages..."
"$PYTHON" -m pip install -r "$APP_DIR/requirements.txt" --quiet

echo "Packages installed."

# ── Start the server ──────────────────────────
PORT="${PORT:-8080}"
echo ""
echo "Starting server on http://localhost:$PORT"
echo "Press Ctrl+C to stop."
echo ""

cd "$APP_DIR"
PORT="$PORT" "$PYTHON" run.py
