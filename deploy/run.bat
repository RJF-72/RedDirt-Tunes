@echo off
REM RedDirt-Tunes Windows Launcher
REM Auto-discovers Python model server and starts Rust client.

echo [reddirt] Booting RedDirt-Tunes...

REM Step 1: Detect Python env
set PYTHON=python
where python > nul 2>&1
if errorlevel 1 (
    where python3 > nul 2>&1
    if errorlevel 1 (
        echo [reddirt] WARNING: Python not found. Model server will not start.
        echo [reddirt] Install Python or start the model server manually.
        goto :client
    ) else (
        set PYTHON=python3
    )
)

REM Step 2: Check if model server already running
curl -f http://127.0.0.1:8765/health > nul 2>&1
if errorlevel 1 (
    echo [reddirt] Model server not detected. Starting...
    start "RedDirt-Model" /min cmd /c "%PYTHON% training\model_server.py --backend ace-step --output-dir .reddirt\output"
    echo [reddirt] Waiting for server to start...
    timeout /t 15 /nobreak > nul
) else (
    echo [reddirt] Model server already running on port 8765.
)

:client
REM Step 3: Start Rust client
echo [reddirt] Starting Rust client...
start "RedDirt-Tunes" cmd /k "target\release\reddirt-tunes.exe"

echo [reddirt] Done. Client and model server should be running.
