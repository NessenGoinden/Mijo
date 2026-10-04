"""Décodage audio/vidéo local avec PyAV (pas de binaire ffmpeg nécessaire)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000


def probe(path: Path | str) -> dict[str, Any]:
    import av

    info: dict[str, Any] = {"duration": None, "has_audio": False, "has_video": False, "width": None, "height": None}
    try:
        with av.open(str(path), metadata_errors="ignore") as c:
            if c.duration:
                info["duration"] = c.duration / av.time_base
            if c.streams.audio:
                info["has_audio"] = True
            if c.streams.video:
                v = c.streams.video[0]
                info["has_video"] = True
                info["width"], info["height"] = v.codec_context.width, v.codec_context.height
                if info["duration"] is None and v.duration and v.time_base:
                    info["duration"] = float(v.duration * v.time_base)
    except Exception as e:
        log.warning("probe %s : %s", path, e)
    return info


def extract_audio(path: Path | str) -> Optional[np.ndarray]:
    """Renvoie l'audio en float32 mono 16 kHz (format attendu par Whisper), ou None."""
    import av

    chunks: list[np.ndarray] = []
    try:
        with av.open(str(path), metadata_errors="ignore") as c:
            if not c.streams.audio:
                return None
            stream = c.streams.audio[0]
            resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
            for frame in c.decode(stream):
                for rf in resampler.resample(frame):
                    chunks.append(rf.to_ndarray().reshape(-1))
            for rf in resampler.resample(None):
                chunks.append(rf.to_ndarray().reshape(-1))
    except Exception as e:
        log.warning("extract_audio %s : %s", path, e)
        return None
    if not chunks:
        return None
    audio = np.concatenate(chunks).astype(np.float32) / 32768.0
    return audio


def _to_pil(frame) -> Image.Image:
    img = frame.to_image()
    if img.width > 1280:
        ratio = 1280 / img.width
        img = img.resize((1280, int(img.height * ratio)))
    return img


def _signature(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L").resize((64, 64)), dtype=np.float32)


def _changed(sig: np.ndarray, last: np.ndarray, diff_threshold: float) -> bool:
    """Vrai si l'image diffère notablement de la précédente (décor OU texte incrusté)."""
    d = np.abs(sig - last)
    return float(d.mean()) >= diff_threshold or float((d > 40).mean()) >= 0.01


def extract_frames(path: Path | str, max_frames: int = 14, diff_threshold: float = 2.5) -> list[Image.Image]:
    """Extrait des images clés réparties sur la vidéo, en éliminant les quasi-doublons."""
    import av

    info = probe(path)
    duration = info.get("duration") or 0.0
    if not info.get("has_video"):
        return []
    # Objectif : ~2 candidats par image finale, mais au plus une candidate par seconde.
    n_candidates = int(max(4, min(max_frames * 2, max(duration, 1.0) / 1.0)))
    if duration <= 0:
        targets = []
    else:
        step = duration / (n_candidates + 1)
        targets = [step * (i + 1) for i in range(n_candidates)]

    candidates: list[tuple[float, Image.Image]] = []
    try:
        with av.open(str(path), metadata_errors="ignore") as c:
            stream = c.streams.video[0]
            stream.thread_type = "AUTO"
            if duration > 240 and targets:
                # Longue vidéo : on se positionne sur chaque instant cible.
                for t in targets:
                    c.seek(int(t / stream.time_base) if stream.time_base else int(t * av.time_base), stream=stream, backward=True, any_frame=False)
                    for frame in c.decode(stream):
                        candidates.append((frame.time or t, _to_pil(frame)))
                        break
            else:
                idx = 0
                for frame in c.decode(stream):
                    if not targets:
                        candidates.append((frame.time or 0.0, _to_pil(frame)))
                        if len(candidates) >= max_frames:
                            break
                        continue
                    t = frame.time if frame.time is not None else 0.0
                    while idx < len(targets) and t >= targets[idx]:
                        candidates.append((t, _to_pil(frame)))
                        idx += 1
                    if idx >= len(targets):
                        break
    except Exception as e:
        log.warning("extract_frames %s : %s", path, e)

    kept: list[Image.Image] = []
    last_sig: Optional[np.ndarray] = None
    for _, img in candidates:
        sig = _signature(img)
        if last_sig is None or _changed(sig, last_sig, diff_threshold):
            kept.append(img)
            last_sig = sig
    if len(kept) > max_frames:
        step = len(kept) / max_frames
        kept = [kept[int(i * step)] for i in range(max_frames)]
    return kept


def frame_at(path: Path | str, t: float = 1.0) -> Optional[Image.Image]:
    import av

    try:
        with av.open(str(path), metadata_errors="ignore") as c:
            if not c.streams.video:
                return None
            stream = c.streams.video[0]
            first = None
            for frame in c.decode(stream):
                if first is None:
                    first = _to_pil(frame)
                if frame.time is not None and frame.time >= t:
                    return _to_pil(frame)
            return first
    except Exception as e:
        log.warning("frame_at %s : %s", path, e)
        return None


def save_thumbnail(img: Image.Image, dest: Path, max_size: int = 800) -> Path:
    img = img.convert("RGB")
    img.thumbnail((max_size, max_size))
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "JPEG", quality=86, optimize=True)
    return dest
