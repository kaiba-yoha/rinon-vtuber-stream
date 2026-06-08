@echo off
set THIS_SCRIPT=%~dp0
set FFMPEG=%THIS_SCRIPT%ffmpeg.exe
if not exist "%FFMPEG%" set FFMPEG=ffmpeg

REM Run this first to check your mic name:
REM %FFMPEG% -list_devices true -f dshow -i dummy

echo Streaming mic to 192.168.0.111:4201 ...
echo Press Ctrl+C to stop.

%FFMPEG% ^
  -f dshow ^
  -i audio="REPLACE_WITH_YOUR_MIC_NAME" ^
  -ar 16000 ^
  -ac 1 ^
  -c:a pcm_s16le ^
  -f s16le ^
  "srt://192.168.0.111:4201"

pause
