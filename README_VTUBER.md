# rinon-vtuber-stream

[rinon-voice-lab](https://github.com/sakugetu/rinon-voice-lab) をベースにした、  
**別PCキャプボ映像 + 別PCマイク → VTuber配信** システム。

## 構成図

```
[別PC]                              [このPC (192.168.0.111)]
  キャプボ映像                           OBS
    ↓                                ├── SRTソース :4200 (別PCの映像)
  OBS ─── SRT :4200 ──────────────→  ├── ブラウザソース (stage.html)
                                      └── YouTube Live RTMP
  マイク                                      ↑
    ↓                               stt_live.py
  send_mic_srt.bat                   ├── SRTリスナー :4201 (マイク受信)
    └── FFmpeg SRT :4201 ─────────→  ├── faster-whisper (文字起こし)
                                      └── /api/speak → Irodori-TTS
                                                ↓
                                         stage.html
                                         ├── キャラ口パク
                                         ├── 表情切替
                                         └── 字幕
```

## 追加ファイル

| ファイル | 説明 |
|---|---|
| `static/stage.html` | OBS Browser Source用アバター画面 |
| `stt_live.py` | マイク音声 → Whisper STT → Irodori TTS |
| `send_mic_srt.bat` | 別PCのマイクをSRTで送信（別PCに配置） |
| `start_vtuber.bat` | 一括起動スクリプト |
| `start_srt_relay.bat` | FFmpeg SRTリレー（デバッグ用） |
| `docs/vtuber_obs_setup.md` | OBS設定ガイド |

## セットアップ

### このPC（受信・配信側）

1. [rinon-voice-lab のセットアップ](https://github.com/sakugetu/rinon-voice-lab)を完了させる
2. 依存パッケージを追加インストール:
   ```
   cd D:\Claude_Projects\Irodori-TTS
   uv pip install faster-whisper sounddevice requests
   ```
3. ファイアウォールでUDPポートを開放（管理者で実行）:
   ```
   netsh advfirewall firewall add rule name="OBS SRT Input UDP 4200" dir=in action=allow protocol=UDP localport=4200 profile=any
   netsh advfirewall firewall add rule name="STT Mic SRT UDP 4201" dir=in action=allow protocol=UDP localport=4201 profile=any
   ```

### OBS設定（このPC）

シーン「VTuber配信」に2ソースを追加:

| レイヤー | 種別 | 設定 |
|---|---|---|
| 上（アバター） | ブラウザ | `http://127.0.0.1:7862/stage.html` / 1920×1080 / 音声キャプチャON |
| 下（映像） | メディアソース | `srt://0.0.0.0:4200?mode=listener` / mpegts |

### 別PC（送信側）

**OBS設定（映像送信）:**

設定 → 配信:
- サービス: カスタム
- サーバー: `srt://192.168.0.111:4200`
- ストリームキー: 空

**マイク送信:**

1. [FFmpeg Windows版](https://ffmpeg.org/download.html) をDL・展開
2. `send_mic_srt.bat` をFFmpegと同フォルダに配置
3. マイク名を確認:
   ```
   ffmpeg.exe -list_devices true -f dshow -i dummy
   ```
4. `send_mic_srt.bat` 内の `REPLACE_WITH_YOUR_MIC_NAME` を書き換えて実行

## 起動手順

1. **このPC**: `start_vtuber.bat` を実行
2. **別PC OBS**: 配信開始（SRT映像送信）
3. **別PC**: `send_mic_srt.bat` を実行（マイク音声送信）
4. 話すとVTuberが喋る

## 動作環境

- Windows 10/11
- Python 3.10+（Irodori-TTS環境）
- NVIDIA GPU（Irodori-TTS + faster-whisper）
- OBS 28以降（SRT対応）
- LAN接続（同一ネットワーク、VPN不使用）

## ネットワークポート

| ポート | プロトコル | 用途 |
|---|---|---|
| 4200 | UDP | 別PCからの映像SRT受信（OBSメディアソース） |
| 4201 | UDP | 別PCからのマイク音声SRT受信（STTパイプライン） |
| 7862 | TCP | Rinon Voice Lab WebUI / API |
