@echo off
REM RedDirt-Tunes Quickstart — Windows
REM One command: installs deps, starts server, runs client.

echo [reddirt] ============================================================
echo [reddirt]  RedDirt-Tunes Quickstart
echo [reddirt]  https://github.com/RJF-72/RedDirt-Tunes
echo [reddirt] ============================================================
echo.

set REDDIRT_ROOT=%~dp0..

REM Step 1: Python environment
echo [reddirt] Checking Python...
python --version > nul 2>&1
if errorlevel 1 (
    echo [reddirt] ERROR: Python is not installed or not on PATH.
    echo [reddirt] Install Python 3.11 from https://python.org
    exit /b 1
)

REM Step 2: Install Python deps (only if not already present)
echo [reddirt] Installing Python dependencies...
python -m pip install -r "%REDdirT_ROOT%\training\requirements.txt" --quiet

REM Step 3: Start model server in background
echo [reddirt] Starting ACE-Step model server...
start "RedDirt-Model" /min cmd /c "python training\model_server.py --model-id Amphion/ACE-Step-1.5B --output-dir .reddirt\output"

REM Step 4: Wait for server
echo [reddirt] Waiting for server to start...
timeout /t 15 /nobreak > nul

REM Step 5: Check server health
curl -f http://127.0.0.1:8765/health > nul 2>&1
if errorlevel 1 (
    echo [reddirt] WARNING: Model server not responding. Check .reddirt\logs\model-server.err.
    echo [reddirt] Retrying anyway...
)

REM Step 6: Build Rust client if not present
echo [reddirt] Building Rust client...
if not exist "target\release\reddirt-tunes.exe" (
    cargo build --release
)

REM Step 7: Run client
echo [reddirt] Launching RedDirt-Tunes...
echo.
cargo run --release
