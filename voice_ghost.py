"""GHOST — voice-enabled local Windows agent.

Groq (llama-3.3-70b-versatile) for the reply, faster-whisper for local
speech-to-text, pyttsx3 for offline text-to-speech. Needs GROQ_API_KEY in .env.
Voice mode can chat and open Notepad, Edge or Calculator; the full skill set
runs in text mode (ghost.py).

Push-to-talk loop:
  • Type `v` + Enter → speak → auto-stops on ~1.5s silence (or 15s max).
  • Or just type your message and press Enter for text mode.
  • Type `exit` to quit.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from dotenv import load_dotenv
from groq import Groq
from faster_whisper import WhisperModel
import pyttsx3
import subprocess
from skills import ALL_TOOLS, DISPATCH

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

logging.basicConfig(
    filename=ROOT / "ghost.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ghost")

# ---- Config -------------------------------------------------------------
MODEL = "llama-3.3-70b-versatile"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

if not GROQ_API_KEY:
    print("ERROR: set GROQ_API_KEY in .env")
    sys.exit(1)

BACKEND = "groq"

chat_client = Groq(api_key=GROQ_API_KEY)

print("Loading Whisper model...")

whisper_model = WhisperModel(
    "medium",
    device="cpu",
    compute_type="int8"
)

engine = pyttsx3.init()

SYSTEM = """
You are GHOST, a Windows automation agent.

Return ONLY valid JSON in this format:

For app opening:
{"action": "open_app", "target": "notepad"}

Allowed targets:
- notepad
- edge
- calc

For normal chat:
{"action": "none", "message": "text here"}

No extra text. No markdown. No explanation.
"""

BANNER = r"""
   ▄████  ██░ ██  ▒█████    ██████ ▄▄▄█████▓
  ██▒ ▀█▒▓██░ ██▒▒██▒  ██▒▒██    ▒ ▓  ██▒ ▓▒
 ▒██░▄▄▄░▒██▀▀██░▒██░  ██▒░ ▓██▄   ▒ ▓██░ ▒░
 ░▓█  ██▓░▓█ ░██ ▒██   ██░  ▒   ██▒░ ▓██▓ ░
 ░▒▓███▀▒░▓█▒░██▓░ ████▓▒░▒██████▒▒  ▒██▒ ░
"""

# ---- Audio I/O ----------------------------------------------------------
SAMPLE_RATE = 16000

def record_until_silence(max_seconds: float = 15.0, silence_seconds: float = 1.5,
                         silence_rms: float = 0.012) -> str:
    print("🎙  listening… (auto-stops on silence)")
    block = 1024
    silence_blocks_needed = int(silence_seconds * SAMPLE_RATE / block)
    max_blocks = int(max_seconds * SAMPLE_RATE / block)
    audio_chunks: list[np.ndarray] = []
    silent_count = 0
    spoken = False

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                        blocksize=block) as stream:
        for _ in range(max_blocks):
            data, _ = stream.read(block)
            audio_chunks.append(data.copy())
            rms = float(np.sqrt(np.mean(data ** 2)))
            if rms > silence_rms:
                spoken = True
                silent_count = 0
            elif spoken:
                silent_count += 1
                if silent_count >= silence_blocks_needed:
                    break

    audio = np.concatenate(audio_chunks, axis=0)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    sf.write(tmp.name, audio, SAMPLE_RATE, subtype="PCM_16")
    tmp.close()
    return tmp.name




# ---- Voice (Whisper STT + OpenAI TTS) ----------------------------------
def speech_to_text(wav_path: str) -> str:
    segments, info = whisper_model.transcribe(
        wav_path,
        beam_size=5
    )

    text = " ".join(
        segment.text
        for segment in segments
    )

    return text.strip()


def text_to_speech(text: str):
    engine.say(text)
    engine.runAndWait()


# ---- Tools --------------------------------------------------------------
def run_windows_action(command: str):
    cmd = command.strip().upper()

    if cmd == "OPEN_NOTEPAD":
        subprocess.Popen("notepad.exe")
        return "Opened Notepad"

    if cmd == "OPEN_EDGE":
        subprocess.Popen("msedge.exe")
        return "Opened Edge browser"

    if cmd == "OPEN_CALC":
        subprocess.Popen("calc.exe")
        return "Opened Calculator"

    return None





# ---- Claude tool-use loop ----------------------------------------------
def think_and_act(user_text: str, history: list) -> str:
    history.append({"role": "user", "content": user_text})

    reply = _loop_groq(history)

    # -------- STEP 2: PARSE LLM OUTPUT --------
    action_result = None

    try:
        data = json.loads(reply)

        if isinstance(data, dict) and data.get("action") == "open_app":
            target = data.get("target", "").lower()

            if target == "notepad":
                subprocess.Popen("notepad.exe")
                action_result = "Opened Notepad"

            elif target == "edge":
                subprocess.Popen("msedge.exe")
                action_result = "Opened Edge browser"

            elif target == "calc":
                subprocess.Popen("calc.exe")
                action_result = "Opened Calculator"

    except Exception:
        # Not JSON → ignore and treat as normal text response
        action_result = None

    if action_result:
        reply = action_result

    return reply
# ---- Groq tool-use loop ----------------------------------------------
def _loop_groq(history):
    msgs = [{"role": "system", "content": SYSTEM}] + history

    r = chat_client.chat.completions.create(
        model=MODEL,
        messages=msgs,
        temperature=0.3,
        max_tokens=1024,
    )

    text = r.choices[0].message.content

    history.append({
        "role": "assistant",
        "content": text
    })

    return text



# ---- Main loop ----------------------------------------------------------
def main() -> None:
    print(BANNER)
    print(f"GHOST voice agent online · model: {MODEL}")
    print(f"Backend: {BACKEND}\n")
    print("Type your message, or `v` to speak. `exit` to quit.\n")
    history: list = []

    while True:
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye."); return
        if not cmd:
            continue
        if cmd.lower() in {"exit", "quit", ":q"}:
            return

        if cmd.lower() == "v":
            wav = record_until_silence()
            try:
                user_text = speech_to_text(wav)
            finally:
                try: os.remove(wav)
                except OSError: pass
            if not user_text:
                print("(nothing heard)\n"); continue
            print(f"you (heard): {user_text}")
        else:
            user_text = cmd

        log.info("user: %s", user_text)
        try:
            reply = think_and_act(user_text, history)
        except Exception as e:
            log.exception("LLM error")
            print(f"⚠ {e}\n"); continue

        if reply:
            print(f"\nGHOST: {reply}\n")
            log.info("assistant: %s", reply)
            try:
                text_to_speech(reply)
            except Exception as e:
                log.warning("TTS failed: %s", e)


if __name__ == "__main__":
    main()
