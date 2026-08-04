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

# DHS Architecture Excel Data Sources
INFO_HARNESS_FILE = DATA_DIR / "Information_Harnessing_Source.xlsx"
KNOWLEDGE_HARNESS_FILE = DATA_DIR / "Knowledge_Harnessing_Source.xlsx"
INFERENCE_HARNESS_FILE = DATA_DIR / "Inference_Harnessing_Source.xlsx"
OUTCOME_HARNESS_FILE = DATA_DIR / "Outcome_Harnessing_Source.xlsx"
BENCHMARK_HARNESS_FILE = DATA_DIR / "Benchmarking_Harnessing_Source.xlsx"
GOVERNANCE_SECURITY_FILE = DATA_DIR / "Governance_Security_Source.xlsx"

# Legacy / Aliases for backward compatibility
KB_FILE_PATH = KNOWLEDGE_HARNESS_FILE
METRICS_FILE_PATH = INFO_HARNESS_FILE
ACCESS_FILE_PATH = GOVERNANCE_SECURITY_FILE
OPERATIONS_FILE_PATH = OUTCOME_HARNESS_FILE

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
    """Check if DHS Excel data sources exist; generate them if missing."""
    dhs_files = [
        INFO_HARNESS_FILE,
        KNOWLEDGE_HARNESS_FILE,
        INFERENCE_HARNESS_FILE,
        OUTCOME_HARNESS_FILE,
        BENCHMARK_HARNESS_FILE,
        GOVERNANCE_SECURITY_FILE,
    ]
    if any(not f.exists() for f in dhs_files):
        print("[Config] DHS Mock Excel files missing. Auto-generating data...")
        from app.data.generate_mock_data import generate_all_mock_data
        generate_all_mock_data(DATA_DIR)
        print("[Config] All 6 DHS Excel data sources ready.")
