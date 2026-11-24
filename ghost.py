"""GHOST — text-only local Windows agent.

Uses Groq (openai/gpt-oss-120b) through the OpenAI-compatible API, with a
tool-calling loop over every skill in skills/. Needs GROQ_API_KEY in .env.

Run with `python ghost.py`. Logs to ghost.log.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from skills import ALL_TOOLS, DISPATCH

ROOT = Path(__file__).parent
print("Running file:", __file__)
print("ROOT:", ROOT)

load_dotenv(ROOT / ".env")

logging.basicConfig(
    filename=ROOT / "ghost.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ghost")

MODEL = "openai/gpt-oss-120b"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

if not GROQ_API_KEY:
    print("ERROR: set GROQ_API_KEY in .env")
    sys.exit(1)

BACKEND = "groq"

chat_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM = (
    "You are GHOST, a personal AI assistant running on the user's Windows PC. "
    "You have real hands: open apps, manipulate files, take screenshots, run "
    "guarded PowerShell. State your plan in one sentence before calling a tool. "
    "Confirm before irreversible actions. Be concise."
)

BANNER = r"""
   ▄████  ██░ ██  ▒█████    ██████ ▄▄▄█████▓
  ██▒ ▀█▒▓██░ ██▒▒██▒  ██▒▒██    ▒ ▓  ██▒ ▓▒
 ▒██░▄▄▄░▒██▀▀██░▒██░  ██▒░ ▓██▄   ▒ ▓██░ ▒░
"""


def _openai_tools() -> list:
    return [{"type": "function", "function": {
        "name": t["name"], "description": t["description"], "parameters": t["input_schema"]
    }} for t in ALL_TOOLS]


def run_tool(name: str, args: dict) -> str:
    fn = DISPATCH.get(name)
    if not fn:
        return json.dumps({"error": f"unknown tool {name}"})
    log.info("tool=%s args=%s", name, args)
    try:
        result = fn(**(args or {}))
    except Exception as e:
        log.exception("tool error")
        result = {"error": str(e)}
    log.info("tool=%s result=%s", name, result)
    return json.dumps(result, default=str)


def _hop_openai(history: list) -> str:
    msgs = [{"role": "system", "content": SYSTEM}] + history

    for _ in range(10):
        r = chat_client.chat.completions.create(
            model=MODEL,
            messages=msgs,
            tools=_openai_tools(),
            tool_choice="auto",
            temperature=0,
            max_tokens=1024,
        )

        msg = r.choices[0].message

        entry = {
            "role": "assistant",
            "content": msg.content or ""
        }

        if msg.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in msg.tool_calls
            ]

        msgs.append(entry)

        if not msg.tool_calls:
            history[:] = [m for m in msgs if m["role"] != "system"]
            return msg.content or ""

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")

                # Remove null values
                args = {
                    k: v
                    for k, v in args.items()
                    if v is not None
                }

            except Exception:
                args = {}

            print(f"  ↳ {tc.function.name}({json.dumps(args)})")

            msgs.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": run_tool(tc.function.name, args)
            })

    return ""



def main() -> None:
    print(BANNER)
    print(f"GHOST online. Model: {MODEL} · Backend: {BACKEND}")
    print("Type 'exit' to quit.\n")
    history: list = []
    while True:
        try:
            user = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye."); return
        if not user: continue
        if user.lower() in {"exit", "quit", ":q"}: return
        history.append({"role": "user", "content": user})
        log.info("user: %s", user)
        try:
            reply = _hop_openai(history)
        except Exception as e:
            log.exception("LLM error")
            print(f"⚠ {e}\n"); continue
        if reply:
            print(f"\nGHOST: {reply}\n")
            log.info("assistant: %s", reply)


if __name__ == "__main__":
    main()
