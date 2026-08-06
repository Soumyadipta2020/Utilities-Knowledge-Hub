"""
Configuration Settings for Utilities Knowledge Hub Chatbot.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"

# Load environment variables from .env file
load_dotenv(PROJECT_ROOT / ".env")

# Server Settings
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
SECRET_KEY = os.getenv("SECRET_KEY", "utilities-knowledge-hub-secret-key-2026")

# OpenRouter / LLM Settings
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", os.getenv("OPENAI_API_KEY", ""))
OPENROUTER_MODEL_NAME = os.getenv("OPENROUTER_MODEL_NAME", os.getenv("LLM_MODEL", "google/gemma-4-26b-a4b-it:free"))
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Legacy aliases for backwards compatibility
OPENAI_API_KEY = OPENROUTER_API_KEY
DEFAULT_MODEL_NAME = OPENROUTER_MODEL_NAME
