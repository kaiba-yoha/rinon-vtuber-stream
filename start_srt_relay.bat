@echo off
setlocal
set FFMPEG=D:\Dev\ffmpeg-7.1-full_build\bin\ffmpeg.exe

echo ================================================
echo  SRT リレー起動中
echo  別PCのOBS送信先: srt://192.168.0.111:4200
echo  OBSメディアソース: udp://127.0.0.1:5200
echo ================================================
echo.
echo 別PCのOBSで配信開始後、映像が届き始めます。
echo 停止するには Ctrl+C を押してください。
echo.

"%FFMPEG%" ^
  -loglevel warning ^
  -i "srt://0.0.0.0:4200?mode=listener&latency=200" ^
  -c copy ^
  -f mpegts ^
  "udp://127.0.0.1:5200?pkt_size=1316"

pause
