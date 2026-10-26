"""Application configuration."""

import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# auto: use Gemini when GOOGLE_API_KEY is present; otherwise use deterministic mock logic.
# gemini: require Gemini.
# mock: always use deterministic logic.
LLM_MODE = os.getenv("LLM_MODE", "auto")

DATABASE_PATH = os.getenv("DATABASE_PATH", "incidents.db")
MAX_TOOL_CALLS = 6
MAX_CONTEXT_TOKENS = 6000
