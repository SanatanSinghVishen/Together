import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Ports for the applications
PORT = int(os.getenv("PORT", 8000))
OPERATOR_MEMORY_PORT = int(os.getenv("OPERATOR_MEMORY_PORT", 8001))
PORTFOLIO_PULSE_PORT = int(os.getenv("PORTFOLIO_PULSE_PORT", 8002))
US_CORRIDOR_AUDITOR_PORT = int(os.getenv("US_CORRIDOR_AUDITOR_PORT", 8003))

# Model Configurations
# Default model to use via OpenRouter (Gemini 3.5 Flash is fast, smart, and extremely cheap)
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "google/gemini-3.5-flash")

# Central Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATASETS_DIR = os.path.join(BASE_DIR, "datasets")
CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", os.path.join(BASE_DIR, "chroma_db"))
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.join(BASE_DIR, "portfolio.db"))
