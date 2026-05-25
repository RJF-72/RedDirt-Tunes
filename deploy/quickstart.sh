#!/usr/bin/env bash
# RedDirt-Tunes Quickstart — Linux / macOS
# One command: installs deps, starts server, runs client.

set -e

REDDIRT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "[reddirt] ============================================================"
echo "[reddirt]  RedDirt-Tunes Quickstart"
echo "[reddirt]  https://github.com/RJF-72/RedDirt-Tunes"
echo "[reddirt] ============================================================"
echo ""

# Step 1: Python
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "[reddirt] ERROR: Python 3 is not installed."
    echo "[reddirt] Install it: apt install python3 python3-pip"
    exit 1
fi

PYTHON="${REDdirT_PYTHON:-$(command -v python3 || command -v python)}"

# Step 2: Python deps
echo "[reddirt] Installing Python dependencies..."
"$PYTHON" -m pip install -r "$REDDIRT_ROOT/training/requirements.txt" --quiet

# Step 3: Start model server
if ! curl -f http://127.0.0.1:8765/health &>/dev/null; then
    echo "[reddirt] Starting ACE-Step model server..."
    nohup "$PYTHON" "$REDDIRT_ROOT/training/model_server.py" \
        --model-id Amphion/ACE-Step-1.5B \
        --output-dir "$REDDIRT_ROOT/.reddirt/output" \
        &> "$REDDIRT_ROOT/.reddirt/logs/model-server.log" &
    echo "[reddirt] Waiting for server..."
    sleep 15
fi

# Step 4: Build Rust client if missing
if [ ! -f "$REDDIRT_ROOT/target/release/reddirt-tunes" ]; then
    echo "[reddirt] Building Rust client..."
    cargo build --release
fi

# Step 5: Run
echo "[reddirt] Launching RedDirt-Tunes..."
"$REDDIRT_ROOT/target/release/reddirt-tunes"
