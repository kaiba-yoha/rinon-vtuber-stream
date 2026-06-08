@echo off
set THIS_SCRIPT=%~dp0
set FFMPEG=%THIS_SCRIPT%ffmpeg.exe
if not exist "%FFMPEG%" set FFMPEG=ffmpeg

REM Run this first to check your mic name:
REM %FFMPEG% -list_devices true -f dshow -i dummy

echo Streaming mic to 192.168.0.111:4201 ...
echo Press Ctrl+C to stop.

:retry
%FFMPEG% ^
  -f dshow ^
  -i audio="REPLACE_WITH_YOUR_MIC_NAME" ^
  -ar 16000 ^
  -ac 1 ^
  -c:a aac ^
  -b:a 64k ^
  -f mpegts ^
  "srt://192.168.0.111:4201?latency=200"

echo Disconnected. Reconnecting in 2 seconds...
timeout /t 2 /nobreak >nul
goto retry
