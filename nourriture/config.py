"""Chemins de données, réglages utilisateur et journalisation.

Toutes les données vivent dans ~/Library/Application Support/Nourriture
(modifiable via la variable d'environnement NOURRITURE_DATA_DIR).
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import threading
from pathlib import Path
from typing import Any

from . import APP_NAME

# ---------------------------------------------------------------------------
# Dossiers
# ---------------------------------------------------------------------------

def _default_data_dir() -> Path:
    env = os.environ.get("NOURRITURE_DATA_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / "Library" / "Application Support" / APP_NAME


DATA_DIR: Path = _default_data_dir()
IMAGES_DIR: Path = DATA_DIR / "images"
MODELS_DIR: Path = DATA_DIR / "models"
CACHE_DIR: Path = DATA_DIR / "cache"
LOG_DIR: Path = DATA_DIR / "logs"
DB_PATH: Path = DATA_DIR / "recipes.db"
SETTINGS_PATH: Path = DATA_DIR / "settings.json"


def ensure_dirs() -> None:
    for d in (DATA_DIR, IMAGES_DIR, MODELS_DIR, CACHE_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def resource_path(*parts: str) -> Path:
    """Chemin vers une ressource embarquée (fonctionne aussi dans le .app PyInstaller)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "nourriture" / Path(*parts)
    return Path(__file__).parent / Path(*parts)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


# ---------------------------------------------------------------------------
# Réglages
# ---------------------------------------------------------------------------

WHISPER_MODELS = {
    "base": "Rapide, qualité correcte (~150 Mo)",
    "small": "Recommandé : bon français, rapide (~500 Mo)",
    "medium": "Très bon, plus lent (~1,5 Go)",
    "large-v3-turbo": "Excellent, lent sur les petits Mac (~1,6 Go)",
}

RECOMMENDED_LLM_MODELS = [
    {"name": "qwen2.5:7b", "label": "Qwen 2.5 7B — recommandé (16 Go de RAM ou plus, ~4,7 Go)"},
    {"name": "qwen2.5:3b", "label": "Qwen 2.5 3B — léger (8 Go de RAM, ~1,9 Go)"},
    {"name": "gemma3:4b", "label": "Gemma 3 4B — léger, bon en français (~3,3 Go)"},
    {"name": "llama3.1:8b", "label": "Llama 3.1 8B — alternative (~4,9 Go)"},
    {"name": "mistral:7b", "label": "Mistral 7B — alternative (~4,1 Go)"},
]

COOKIE_BROWSERS = ["", "chrome", "safari", "firefox", "brave", "edge", "chromium", "opera", "vivaldi"]

DEFAULT_SETTINGS: dict[str, Any] = {
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "qwen2.5:7b",
    "whisper_model": "small",
    "transcribe_enabled": True,
    "ocr_enabled": True,
    "always_analyze_video": False,
    "max_frames": 14,
    "cookies_browser": "",
    "cookies_file": "",
    "ui_theme": "auto",
    "default_servings": 4,
}

_settings_lock = threading.Lock()
_settings_cache: dict[str, Any] | None = None


def load_settings() -> dict[str, Any]:
    global _settings_cache
    with _settings_lock:
        if _settings_cache is not None:
            return dict(_settings_cache)
        data: dict[str, Any] = {}
        if SETTINGS_PATH.exists():
            try:
                data = json.loads(SETTINGS_PATH.read_text("utf-8"))
            except Exception:  # fichier corrompu → valeurs par défaut
                data = {}
        merged = {**DEFAULT_SETTINGS, **{k: v for k, v in data.items() if k in DEFAULT_SETTINGS}}
        _settings_cache = merged
        return dict(merged)


def save_settings(update: dict[str, Any]) -> dict[str, Any]:
    global _settings_cache
    current = load_settings()
    for k, v in update.items():
        if k in DEFAULT_SETTINGS:
            current[k] = v
    ensure_dirs()
    tmp = SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(SETTINGS_PATH)
    with _settings_lock:
        _settings_cache = dict(current)
    return dict(current)


# ---------------------------------------------------------------------------
# Journalisation
# ---------------------------------------------------------------------------

_logging_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    global _logging_configured
    if _logging_configured:
        return
    ensure_dirs()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(level)
    fh = logging.handlers.RotatingFileHandler(LOG_DIR / "nourriture.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    if not is_frozen() or os.environ.get("NOURRITURE_DEBUG"):
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        root.addHandler(sh)
    for noisy in ("httpx", "httpcore", "urllib3", "uvicorn.access", "faster_whisper", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _logging_configured = True
