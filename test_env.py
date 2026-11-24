from dotenv import load_dotenv
from pathlib import Path
import os

ROOT = Path(__file__).parent

print("ROOT =", ROOT)

loaded = load_dotenv(ROOT / ".env")

print("Loaded =", loaded)

print("KEY =", os.getenv("GEMINI_API_KEY"))