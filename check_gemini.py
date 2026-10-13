"""Check that your Gemini API key and model work. Run: python check_gemini.py"""
import os
import sys

from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

key = os.getenv("GEMINI_API_KEY")
if not key:
    sys.exit("GEMINI_API_KEY is not set in this terminal.\n"
             'PowerShell:  $env:GEMINI_API_KEY="your_key"')

from google import genai

client = genai.Client(api_key=key)
models = [os.getenv("GEMINI_MODEL")] if os.getenv("GEMINI_MODEL") else [
    "gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash"]

for m in models:
    try:
        r = client.models.generate_content(model=m, contents="Reply with the single word: ready")
        print(f"OK   {m} -> {r.text.strip()[:40]}")
    except Exception as e:
        msg = str(e)
        hint = ("model name not found or retired" if "404" in msg or "NOT_FOUND" in msg
                else "quota or rate limit hit (429): wait a minute or check AI Studio" if "429" in msg or "RESOURCE_EXHAUSTED" in msg
                else "API key problem (invalid, restricted, or wrong project)" if "400" in msg or "403" in msg or "API key" in msg
                else "see message")
        print(f"FAIL {m} -> {hint}\n     {msg[:160]}")
