# RedDirt-Tunes Windows Service Installer
# Registers the Rust client as a Windows service using NSSM (Non-Sucking Service Manager).

$ErrorActionPreference = "Stop"

$ServiceName = "RedDirt-Tunes"
$Root = Resolve-Path "$PSScriptRoot\.."
$Binary = "$Root\target\release\reddirt-tunes.exe"
$ModelScript = "$Root\training\model_server.py"
$OutputDir = "$Root\.reddirt\output"
$LogDir = "$Root\.reddirt\logs"

Write-Host "[reddirt] Installing Windows service: $ServiceName"

# Ensure output dirs exist
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

# NSSM download if missing
$nssm = "$Root\deploy\windows\nssm.exe"
if (-not (Test-Path $nssm)) {
    Write-Host "[reddirt] Downloading NSSM..."
    $url = "https://nssm.cc/release/nssm-2.24.zip"
    $zip = "$env:TEMP\nssm.zip"
    Invoke-WebRequest -Uri $url -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath "$env:TEMP\nssm" -Force
    Copy-Item "$env:TEMP\nssm\nssm-2.24\win64\nssm.exe" $nssm -Force
}

# Create wrapper script for model server
$wrapper = "$Root\deploy\windows\start-model.bat"
@"
@echo off
if not exist "$OutputDir" mkdir "$OutputDir"
python "$ModelScript" --backend ace-step --output-dir "$OutputDir" --port 8765
"@ | Set-Content -Path $wrapper -Encoding ASCII

# Register model server service
Write-Host "[reddirt] Registering model server service..."
& $nssm install "${ServiceName}-Model" $wrapper
& $nssm set "${ServiceName}-Model" AppDirectory $Root
& $nssm set "${ServiceName}-Model" AppStdout "$LogDir\model-server.log"
& $nssm set "${ServiceName}-Model" AppStderr "$LogDir\model-server.err"

# Register Rust client service
Write-Host "[reddirt] Registering Rust client service..."
& $nssm install $ServiceName $Binary
& $nssm set $ServiceName AppDirectory $Root
& $nssm set $ServiceName AppEnvironmentExtra "REDdirT_MODEL_URL=http://127.0.0.1:8765"
& $nssm set $ServiceName AppStdout "$LogDir\reddirt-client.log"
& $nssm set $ServiceName AppStderr "$LogDir\reddirt-client.err"

# Start services
Start-Service "${ServiceName}-Model"
Start-Service $ServiceName

Write-Host "[reddirt] Service installed and started."
Write-Host "[reddirt] Logs: $LogDir"
