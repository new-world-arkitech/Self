# Self/src/engine/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
ENGINE_DIR = Path(__file__).resolve().parent
SRC_DIR = ENGINE_DIR.parent
ROOT_DIR = SRC_DIR.parent

# Load environment variables from root .env
ENV_FILE = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)

# Application Settings
APP_NAME = os.getenv("APP_NAME", "Self")
APP_ENV = os.getenv("APP_ENV", "development")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "self_local_development_secret_key")

# Storage Paths
STATE_MATRIX_FILE = ROOT_DIR / os.getenv("STATE_MATRIX_FILE", "./src/engine/state_matrix.json")
JOURNAL_LEDGER_FILE = ROOT_DIR / os.getenv("JOURNAL_LEDGER_FILE", "./src/engine/journal_ledger.json")
ACCEPTANCE_TEST_REPORT = ROOT_DIR / os.getenv("ACCEPTANCE_TEST_REPORT", "./src/engine/client_acceptance_test_report.html")
MODELS_DIR = ROOT_DIR / os.getenv("MODELS_DIR", "./public/models")

# Life Domain Configuration
DOMAINS = {
    "Self.career": {
        "path": ROOT_DIR / os.getenv("DOMAIN_CAREER_PATH", "./src/Self.career"),
        "attribute": "armor_and_gear",
        "xp_per_page": int(os.getenv("XP_PER_PAGE_CAREER", "15")),
        "xp_per_task": int(os.getenv("XP_PER_TASK_CAREER", "50")),
    },
    "Self.credit": {
        "path": ROOT_DIR / os.getenv("DOMAIN_CREDIT_PATH", "./src/Self.credit"),
        "attribute": "material_shader_and_aura",
        "xp_per_page": int(os.getenv("XP_PER_PAGE_CREDIT", "10")),
        "xp_per_task": int(os.getenv("XP_PER_TASK_CREDIT", "75")),
    },
    "Self.knowledge": {
        "path": ROOT_DIR / os.getenv("DOMAIN_KNOWLEDGE_PATH", "./src/Self.knowledge"),
        "attribute": "neural_hud_and_glyphs",
        "xp_per_page": int(os.getenv("XP_PER_PAGE_KNOWLEDGE", "25")),
        "xp_per_task": int(os.getenv("XP_PER_TASK_KNOWLEDGE", "40")),
    },
    "Self.temple": {
        "path": ROOT_DIR / os.getenv("DOMAIN_TEMPLE_PATH", "./src/Self.temple"),
        "attribute": "base_mesh_and_vitality",
        "xp_per_page": int(os.getenv("XP_PER_PAGE_TEMPLE", "20")),
        "xp_per_task": int(os.getenv("XP_PER_TASK_TEMPLE", "60")),
    },
    "Self.legal": {
        "path": ROOT_DIR / os.getenv("DOMAIN_LEGAL_PATH", "./src/Self.legal"),
        "attribute": "base_mesh_and_vitality",
        "xp_per_page": 10,
        "xp_per_task": 50,
    },
}

# Psychometric & Verification Parameters
QUIZ_PASS_THRESHOLD = float(os.getenv("QUIZ_PASS_THRESHOLD", "0.80"))
ABANDONMENT_PENALTY_WEIGHT = float(os.getenv("ABANDONMENT_PENALTY_WEIGHT", "1.5"))
DAILY_STREAK_DECAY_RATE = float(os.getenv("DAILY_STREAK_DECAY_RATE", "0.05"))
