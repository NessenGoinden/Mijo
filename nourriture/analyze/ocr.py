"""Reconnaissance de texte à l'écran avec le framework Vision de macOS (local, gratuit)."""
from __future__ import annotations

import io
import logging
import re
from typing import Iterable, Optional

from PIL import Image

from ..models import normalize_text

log = logging.getLogger(__name__)

_NOISE_PATTERNS = [
    re.compile(r"^@[a-z0-9_.]{2,}$", re.I),                       # @pseudo seul
    re.compile(r"^[a-z0-9]*[._][a-z0-9_.]*$", re.I),               # pseudo du type chef.test / chef_test
    re.compile(r"^(instagram|reels?|tiktok|youtube|suivre|follow|like|partager|share|abonne[z]?-?toi|abonnez-vous)$", re.I),
    re.compile(r"^[\W_]+$"),                           # ponctuation uniquement
]


def _pil_to_cgimage(img: Image.Image):
    import Quartz
    from Foundation import NSData

    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    data = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
    src = Quartz.CGImageSourceCreateWithData(data, None)
    if src is None:
        return None
    return Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)


def ocr_image(img: Image.Image, languages: Iterable[str] = ("fr-FR", "en-US"), min_confidence: float = 0.3) -> list[dict]:
    """Renvoie les lignes de texte reconnues (texte, confiance, position y de haut en bas)."""
    import Vision
    import objc

    results: list[dict] = []
    with objc.autorelease_pool():
        cg = _pil_to_cgimage(img)
        if cg is None:
            return results
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        req.setRecognitionLanguages_(list(languages))
        req.setUsesLanguageCorrection_(True)
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
        ok, err = handler.performRequests_error_([req], None)
        if not ok:
            log.warning("Vision OCR : %s", err)
            return results
        for obs in req.results() or []:
            cands = obs.topCandidates_(1)
            if not cands:
                continue
            c = cands[0]
            conf = float(c.confidence())
            text = str(c.string()).strip()
            if conf < min_confidence or not text:
                continue
            bbox = obs.boundingBox()
            y_top = 1.0 - (bbox.origin.y + bbox.size.height)
            results.append({"text": text, "confidence": round(conf, 2), "y": y_top, "x": bbox.origin.x})
    results.sort(key=lambda r: (round(r["y"], 2), r["x"]))
    return results


def _is_noise(line: str) -> bool:
    if len(line) < 2:
        return True
    return any(p.match(line) for p in _NOISE_PATTERNS)


def ocr_frames(frames: list[Image.Image], progress=None) -> str:
    """OCR de plusieurs images → lignes uniques, dans l'ordre d'apparition."""
    seen: set[str] = set()
    lines: list[str] = []
    for i, img in enumerate(frames):
        if progress:
            progress(f"Lecture du texte à l'écran ({i + 1}/{len(frames)})…")
        try:
            for r in ocr_image(img):
                text = re.sub(r"\s+", " ", r["text"]).strip()
                key = normalize_text(text)
                if _is_noise(text) or key in seen:
                    continue
                seen.add(key)
                lines.append(text)
        except Exception as e:  # pragma: no cover
            log.warning("OCR image %d : %s", i, e)
    return "\n".join(lines)
