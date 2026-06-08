@echo off
setlocal
cd /d "%~dp0"
if "%IRODORI_ROOT%"=="" set "IRODORI_ROOT=%~dp0..\Irodori-TTS"
for %%I in ("%IRODORI_ROOT%") do set "IRODORI_ROOT=%%~fI"

echo Starting Rinon Voice Lab...
start "RinonVoiceLab" "%IRODORI_ROOT%\.venv\Scripts\python.exe" app.py

echo Waiting for server...
:wait_loop
timeout /t 1 /nobreak >nul
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:7862/api/status | findstr /C:"200" >/dev/null 2>&1
if errorlevel 1 goto wait_loop
echo Server ready.

start "" "http://127.0.0.1:7862/stage.html"

echo STT pipeline starting (remote mic via SRT port 4201)...
echo On the other PC, run send_mic_srt.bat after setting your mic name.
echo Press Ctrl+C to stop.
echo.
"%IRODORI_ROOT%\.venv\Scripts\python.exe" stt_live.py --model small --device cuda --lang ja --srt-port 4201

pause
