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

KB_FILE_PATH = DATA_DIR / "Knowledge_Base.xlsx"
METRICS_FILE_PATH = DATA_DIR / "Live_Metrics.xlsx"
ACCESS_FILE_PATH = DATA_DIR / "Metadata_Access.xlsx"
OPERATIONS_FILE_PATH = DATA_DIR / "Business_Operations.xlsx"

# Server Settings
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
SECRET_KEY = os.getenv("SECRET_KEY", "utilities-knowledge-hub-secret-key-2026")

# OpenRouter / LLM Settings
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", os.getenv("OPENAI_API_KEY", ""))
OPENROUTER_MODEL_NAME = os.getenv("OPENROUTER_MODEL_NAME", os.getenv("LLM_MODEL", "openai/gpt-4o-mini"))
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Legacy aliases for backwards compatibility
OPENAI_API_KEY = OPENROUTER_API_KEY
DEFAULT_MODEL_NAME = OPENROUTER_MODEL_NAME


def ensure_mock_data_exists() -> None:
    """Check if Excel mock data files exist; generate them if missing."""
    if not (KB_FILE_PATH.exists() and METRICS_FILE_PATH.exists() and ACCESS_FILE_PATH.exists() and OPERATIONS_FILE_PATH.exists()):
        print("[Config] Mock Excel files missing. Auto-generating data...")
        from app.data.generate_mock_data import generate_all_mock_data
        generate_all_mock_data(DATA_DIR)
        print("[Config] Mock datasets ready.")
