#!/usr/bin/env bash
# RedDirt-Tunes Linux/macOS Launcher
# Auto-discovers Python model server and starts Rust client.

set -e

REDDIRT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL_URL="${REDdirT_MODEL_URL:-http://127.0.0.1:8765}"

echo "[reddirt] Booting RedDirt-Tunes..."

# Step 1: Detect Python
PYTHON=""
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
fi

# Step 2: Check if model server running
if curl -f "$MODEL_URL/health" &>/dev/null; then
    echo "[reddirt] Model server already running at $MODEL_URL"
else
    if [ -z "$PYTHON" ]; then
        echo "[reddirt] WARNING: Python not found. Model server will not start."
        echo "[reddirt] Install Python or use Docker Compose: docker-compose up"
    else
        echo "[reddirt] Model server not detected. Starting..."
        nohup "$PYTHON" "$REDDIRT_ROOT/training/model_server.py" \
            --backend ace-step \
            --output-dir "$REDDIRT_ROOT/.reddirt/output" \
            &>/dev/null &
        PID=$!
        echo "[reddirt] Model server PID: $PID"
        sleep 15
    fi
fi

# Step 3: Start Rust client
if [ -f "$REDDIRT_ROOT/target/release/reddirt-tunes" ]; then
    echo "[reddirt] Starting Rust client..."
    "$REDDIRT_ROOT/target/release/reddirt-tunes"
else
    echo "[reddirt] ERROR: Binary not found. Run 'cargo build --release' first."
    exit 1
fi
