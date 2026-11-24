# GHOST · AI Windows Desktop Agent (with Voice)

GHOST is an AI agent that runs on your Windows PC. You tell it what you want in
plain English (typed or spoken) and an LLM decides which tools to run: open apps,
find and manage files, take screenshots, run PowerShell, or do scope-gated
bug-bounty recon. Anything destructive asks for your `[y/N]` first.

## 🎬 Demo Video

Watch GHOST AI in action: **[Demo video](https://lnkd.in/p/d34t664R)**

---

## What's inside

| Mode | File | What it does |
|---|---|---|
| **Text mode** (full agent) | `ghost.py` | Groq `openai/gpt-oss-120b` with a tool-calling loop over every skill below. |
| **Voice mode** | `voice_ghost.py` | Speak with `v`, it transcribes locally (faster-whisper) and replies out loud (pyttsx3). Uses Groq `llama-3.3-70b-versatile`. Can chat and open Notepad, Edge or Calculator. |
| **Computer use** (opt-in, beta) | `computer_use.py` | Claude sees the screen and clicks/types. Needs `ANTHROPIC_API_KEY`. **Sandbox VM only.** |

### Skills (text mode)

* ✋ **Desktop** — `get_current_time`, `calculate`, `open_app`, `search_files`,
  `file_action` (move / copy / delete, confirmed), `screenshot`,
  `run_powershell` (always confirmed)
* 🛡 **Bug-bounty pack** — for **authorised testing only**:
  * Scope gate: `scope_confirm` — every active probe is blocked until the target is confirmed in scope
  * Recon: `passive_recon` (crt.sh + DNS), `tech_fingerprint`, `security_headers`,
    `waybackurls`, `js_endpoint_extractor`, `spf_dkim_dmarc`, `ssl_analyser`
  * Active (scope-gated + confirmed): `misconfig_sweep`, `port_scan` (top 100 TCP),
    `directory_brute`, `graphql_introspect`, `subdomain_takeover_check`
  * Utilities: `cve_lookup` (NIST NVD), `hibp_check`, `hash_id`, `decode_toolkit`,
    `draft_report` (HackerOne-style markdown), `bug_bounty_workflow`

> ⚠ Use the bug-bounty skills only on programs that have authorised you to test
> (HackerOne, Bugcrowd, Intigriti, YesWeHack, etc.). Unauthorised scanning is a
> crime in most countries.

---

## Setup (Windows)

**1. Install Python 3.11+** from https://www.python.org/downloads/ and tick
**"Add python.exe to PATH"** in the installer. Check with `python --version`.

**2. Get the code**

```powershell
git clone https://github.com/v-s-abhishek/Ghost-ai.git
cd Ghost-ai
```

**3. Install** — double-click **`setup.bat`**. It creates a `.venv`, installs
`requirements.txt`, copies `.env.example` to `.env` and opens it in Notepad.

Manual alternative:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

> If PowerShell says *"running scripts is disabled"*, run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and answer **Y**.

**4. Add your API key** — get a free key at https://console.groq.com/keys and put
it in `.env`:

```env
GROQ_API_KEY=gsk_your_key_here
```

`.env` is in `.gitignore`, so your key never gets committed.

---

## Running it

**Text mode (full agent):** double-click `run_text.bat`, or `python ghost.py`.

```
> what time is it?
> find all PDFs in my Downloads folder
> take a screenshot
> calculate 1248 divided by 32
> confirm scope for example.com, then check its security headers
```

**Voice mode:** double-click `run_voice.bat`, or `python voice_ghost.py`.
The first start downloads the Whisper `medium` model (~1.5 GB).

| You type | What happens |
|---|---|
| `v` then Enter | Mic opens. Speak. It stops ~1.5 s after you go quiet, transcribes locally and speaks the reply. |
| Any other text | Sent as a text message. |
| `exit` | Quit. |

**Computer use (sandbox VM only):** add `ANTHROPIC_API_KEY` to `.env`, then

```powershell
python computer_use.py "open notepad and write hello world"
```

---

## Add your own skill

Skills live in `skills/__init__.py`.

1. Write a function: `def my_skill(arg1: str) -> dict: ...`
2. Add its schema (`name`, `description`, `input_schema`) to `ALL_TOOLS`.
3. Add the function to `DISPATCH`.

Restart `ghost.py` and the model can call it.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ERROR: set GROQ_API_KEY in .env` | Create `.env` from `.env.example` and paste your Groq key. |
| `python : not recognised` | Re-run the Python installer with **"Add to PATH"** ticked. |
| `setup.bat` closes instantly | Open PowerShell, `cd` to the folder and run `.\setup.bat` to see the error. |
| Mic records nothing | Windows Settings → Privacy & Security → **Microphone** → allow apps. Test with `python -c "import sounddevice; print(sounddevice.query_devices())"`. |
| `ModuleNotFoundError` | The venv isn't active. Run `.\.venv\Scripts\Activate.ps1` first, or use the `.bat` launchers. |

---

## Safety

* Run under a **non-admin Windows account**, so a misread command can't do much damage.
* `file_action` deletes/moves and `run_powershell` **always** prompt `[y/N]`. Don't remove these prompts.
* Every tool call and result is logged to `ghost.log` next to the script.
* `computer_use.py` is off by default. Only run it inside a sandboxed VM.
