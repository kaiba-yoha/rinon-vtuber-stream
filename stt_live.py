"""
stt_live.py — Real-time STT → Irodori-TTS VTuber pipeline

Usage (local mic):
  python stt_live.py [--model small] [--device cuda] [--lang ja]

Usage (remote mic via SRT from another PC):
  python stt_live.py --srt-port 4201
  # On the other PC, run send_mic_srt.bat

Dependencies (install once):
  pip install faster-whisper sounddevice numpy requests
"""
import argparse
import queue
import subprocess
import sys
import threading
import time

import numpy as np
import requests
import sounddevice as sd
from faster_whisper import WhisperModel

# ---- Config defaults ----
DEFAULT_API   = "http://127.0.0.1:7862"
DEFAULT_MODEL = "small"       # tiny / base / small / medium / large-v3
DEFAULT_LANG  = "ja"
DEFAULT_DEVICE = "cuda"       # cuda / cpu / auto
DEFAULT_THRESH = 0.018        # RMS threshold for voice activity
DEFAULT_SAMPLERATE = 16000
DEFAULT_BLOCKSIZE  = 1024     # ~64ms per block at 16kHz
DEFAULT_SILENCE_BLOCKS = 18   # ~1.1s of silence → end of utterance
MAX_SPEECH_BLOCKS = 400       # ~25s max utterance length
DEFAULT_CAPTION = (
    "Native Japanese young adult woman, cute anime assistant voice, "
    "warm and intimate conversational acting, slightly teasing little-devil smile, "
    "soft breath, gentle emotional nuance, clear pronunciation, clean studio sound."
)


FFMPEG = r"D:\Dev\ffmpeg-7.1-full_build\bin\ffmpeg.exe"


def list_devices():
    print(sd.query_devices())


def read_audio_from_udp(port: int, samplerate: int, blocksize: int, audio_q: queue.Queue):
    """UDPで raw s16le PCM を受信してqueueに流す。再接続不要・シンプル。"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))
    sock.settimeout(5.0)
    bytes_per_block = blocksize * 2  # int16 = 2 bytes
    buf = bytearray()
    print(f"[udp] Waiting for mic stream on UDP port {port}...")
    while True:
        try:
            data, addr = sock.recvfrom(65536)
            buf.extend(data)
            while len(buf) >= bytes_per_block:
                chunk = bytes(buf[:bytes_per_block])
                del buf[:bytes_per_block]
                block = np.frombuffer(chunk, dtype=np.int16)
                audio_q.put(block)
        except socket.timeout:
            pass  # 無音期間は継続待機


def rms(block: np.ndarray) -> float:
    return float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))


def send_speak(api_base: str, text: str, caption: str, emoji: str = "") -> bool:
    payload = {
        "text": text,
        "caption": caption,
        "speakerSlot": "main",
        "steps": 12,
        "speechRate": "normal",
    }
    if emoji:
        payload["emoji"] = emoji
    try:
        r = requests.post(f"{api_base}/api/speak", json=payload, timeout=60)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[speak] Error: {e}", file=sys.stderr)
        return False


def transcribe_and_send(
    model: WhisperModel,
    audio: np.ndarray,
    lang: str,
    api_base: str,
    caption: str,
    samplerate: int,
):
    """Transcribe audio array and POST to /api/speak."""
    audio_f32 = audio.astype(np.float32) / 32768.0
    segments, info = model.transcribe(
        audio_f32,
        language=lang,
        vad_filter=True,
        beam_size=3,
        best_of=3,
        temperature=0.0,
        without_timestamps=True,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    if not text:
        print("[stt] (empty transcript, skipped)")
        return
    print(f"[stt] → {text}")
    ok = send_speak(api_base, text, caption)
    if ok:
        print("[speak] queued ✓")


def run(args):
    if args.list_devices:
        list_devices()
        return

    print(f"[init] Loading Whisper model '{args.model}' on {args.device}...")
    model = WhisperModel(
        args.model,
        device=args.device,
        compute_type="float16" if args.device == "cuda" else "int8",
    )
    print("[init] Model ready.")

    audio_q: queue.Queue = queue.Queue()

    # ---- Audio source: SRT (remote mic) or local sounddevice ----
    if args.srt_port:
        t = threading.Thread(
            target=read_audio_from_udp,
            args=(args.srt_port, args.samplerate, args.blocksize, audio_q),
            daemon=True,
        )
        t.start()
    else:
        def callback(indata, frames, time_info, status):
            if status:
                print(f"[mic] {status}", file=sys.stderr)
            audio_q.put(indata[:, 0].copy())

    # ---- VAD state machine ----
    state = "idle"
    speech_blocks: list[np.ndarray] = []
    silence_count = 0

    def process_loop():
        nonlocal state, speech_blocks, silence_count
        while True:
            block = audio_q.get()
            level = rms(block)
            is_voice = level > args.threshold

            if state == "idle":
                if is_voice:
                    state = "speech"
                    speech_blocks = [block]
                    silence_count = 0
                    print("[stt] speech start")

            elif state == "speech":
                speech_blocks.append(block)
                if not is_voice:
                    silence_count += 1
                else:
                    silence_count = 0

                too_long = len(speech_blocks) >= MAX_SPEECH_BLOCKS
                end_of_speech = silence_count >= args.silence_blocks

                if end_of_speech or too_long:
                    state = "idle"
                    audio = np.concatenate(speech_blocks).astype(np.int16)
                    speech_blocks = []
                    silence_count = 0
                    duration = len(audio) / args.samplerate
                    print(f"[stt] speech end ({duration:.1f}s), transcribing...")
                    threading.Thread(
                        target=transcribe_and_send,
                        args=(model, audio, args.lang, args.api, args.caption, args.samplerate),
                        daemon=True,
                    ).start()

    proc_thread = threading.Thread(target=process_loop, daemon=True)
    proc_thread.start()

    if args.srt_port:
        print(f"[udp] Mic stream UDP port {args.srt_port} | lang={args.lang}")
        print(f"[udp] On the other PC, run: send_mic_udp.bat")
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[stt] Stopped.")
    else:
        print(f"[mic] Listening on device {args.device_index or 'default'} "
              f"(threshold={args.threshold}, lang={args.lang})")
        print("[mic] Speak into the mic. Ctrl+C to stop.\n")
        with sd.InputStream(
            samplerate=args.samplerate,
            blocksize=args.blocksize,
            device=args.device_index,
            channels=1,
            dtype="int16",
            callback=callback,
        ):
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n[stt] Stopped.")


def main():
    p = argparse.ArgumentParser(description="Real-time STT → VTuber TTS pipeline")
    p.add_argument("--model",         default=DEFAULT_MODEL,
                   help="Whisper model size: tiny/base/small/medium/large-v3")
    p.add_argument("--device",        default=DEFAULT_DEVICE,
                   help="Whisper device: cuda / cpu / auto")
    p.add_argument("--lang",          default=DEFAULT_LANG,
                   help="Language code, e.g. ja / en")
    p.add_argument("--threshold",     type=float, default=DEFAULT_THRESH,
                   help="RMS voice activity threshold (0.0–1.0)")
    p.add_argument("--silence-blocks", type=int, default=DEFAULT_SILENCE_BLOCKS,
                   dest="silence_blocks",
                   help="Silent blocks before utterance ends")
    p.add_argument("--api",           default=DEFAULT_API,
                   help="Rinon Voice Lab base URL")
    p.add_argument("--caption",       default=DEFAULT_CAPTION,
                   help="Irodori TTS acting caption")
    p.add_argument("--samplerate",    type=int, default=DEFAULT_SAMPLERATE)
    p.add_argument("--blocksize",     type=int, default=DEFAULT_BLOCKSIZE)
    p.add_argument("--device-index",  type=int, default=None,
                   dest="device_index",
                   help="sounddevice input device index (see --list-devices)")
    p.add_argument("--list-devices",  action="store_true", dest="list_devices",
                   help="Print available audio devices and exit")
    p.add_argument("--srt-port",      type=int, default=None, dest="srt_port",
                   help="Receive mic audio via SRT from another PC on this port (e.g. 4201)")
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
