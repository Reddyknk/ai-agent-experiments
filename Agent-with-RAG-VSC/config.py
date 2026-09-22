import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DEFAULT_LLM_MODEL = "gemma-4-26b-a4b-it"
PORT = int(os.getenv("PORT", "5000"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", DEFAULT_LLM_MODEL)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
HF_TOKEN = os.getenv("HF_TOKEN")
PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_DIR = PROJECT_ROOT / "database"
SKILLS_DIR = PROJECT_ROOT / "skills"
SAMPLE_DOCS_DIR = PROJECT_ROOT / "sample_docs"
