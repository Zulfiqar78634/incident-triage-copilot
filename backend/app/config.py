"""Application configuration."""

import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
AGENT_MODE = os.getenv("AGENT_MODE", "mock")
DATABASE_PATH = os.getenv("DATABASE_PATH", "incidents.db")
MAX_TOOL_CALLS = 6
MAX_CONTEXT_TOKENS = 6000
