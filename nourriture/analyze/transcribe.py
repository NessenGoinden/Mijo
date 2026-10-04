"""Transcription audio locale avec faster-whisper (CTranslate2, CPU, gratuit)."""
from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

from ..config import MODELS_DIR

log = logging.getLogger(__name__)

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

WHISPER_DIR = MODELS_DIR / "whisper"

_MODEL_REPOS = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}

# Phrases typiques des hallucinations de Whisper sur du silence ou de la musique.
_HALLUCINATIONS = [
    "sous-titres réalisés", "sous-titrage", "amara.org", "merci d'avoir regardé", "abonnez-vous",
    "thank you for watching", "thanks for watching", "subtitles by", "sous-titres par", "www.", "♪",
]

_models: dict[str, Any] = {}
_lock = threading.Lock()


def model_is_downloaded(name: str) -> bool:
    repo = _MODEL_REPOS.get(name)
    if not repo:
        return False
    folder = WHISPER_DIR / ("models--" + repo.replace("/", "--"))
    return folder.exists() and any(folder.rglob("model.bin"))


def download_model(name: str) -> None:
    from faster_whisper import download_model as _dl

    WHISPER_DIR.mkdir(parents=True, exist_ok=True)
    _dl(name, cache_dir=str(WHISPER_DIR))


def get_model(name: str):
    from faster_whisper import WhisperModel

    with _lock:
        if name not in _models:
            WHISPER_DIR.mkdir(parents=True, exist_ok=True)
            log.info("Chargement du modèle Whisper « %s »", name)
            _models.clear()  # un seul modèle en mémoire à la fois
            _models[name] = WhisperModel(name, device="cpu", compute_type="int8", download_root=str(WHISPER_DIR))
        return _models[name]


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def transcribe(
    audio: np.ndarray | str | Path,
    model_name: str = "small",
    language: Optional[str] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> dict[str, Any]:
    """Transcrit un tableau audio (float32 16 kHz) ou un fichier. Renvoie texte, langue, segments."""
    if isinstance(audio, np.ndarray) and audio.size < 16000 * 0.5:
        return {"text": "", "language": None, "segments": [], "duration": 0.0}
    model = get_model(model_name)
    if progress:
        progress("Transcription de l'audio…")
    segments_iter, info = model.transcribe(
        audio if isinstance(audio, np.ndarray) else str(audio),
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
    )
    segments = []
    texts = []
    for seg in segments_iter:
        t = _clean_text(seg.text)
        if not t:
            continue
        low = t.lower()
        if any(h in low for h in _HALLUCINATIONS):
            continue
        if getattr(seg, "no_speech_prob", 0) > 0.85 and getattr(seg, "avg_logprob", 0) < -1.0:
            continue
        segments.append({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": t})
        texts.append(t)
    # Supprime les répétitions en boucle (hallucination classique).
    deduped: list[str] = []
    for t in texts:
        if len(deduped) >= 2 and t == deduped[-1] == deduped[-2]:
            continue
        deduped.append(t)
    return {
        "text": " ".join(deduped).strip(),
        "language": getattr(info, "language", None),
        "language_probability": round(float(getattr(info, "language_probability", 0) or 0), 2),
        "duration": round(float(getattr(info, "duration", 0) or 0), 1),
        "segments": segments,
    }
