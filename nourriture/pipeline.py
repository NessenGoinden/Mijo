"""Orchestration d'un import : récupération → analyse locale → structuration par l'IA.

Chaque import est un « job » exécuté dans un thread de fond ; l'interface interroge son état.
"""
from __future__ import annotations

import logging
import re
import shutil
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from . import config
from .analyze import media, ocr, transcribe
from .db import Database
from .fetch import instagram
from .llm.ollama import OllamaClient, OllamaError
from .llm.prompts import SYSTEM_PROMPT, build_user_prompt
from .models import LLM_RECIPE_SCHEMA, ImportRequest, Recipe, RecipeContent, RecipeSources, new_id, now_iso

log = logging.getLogger(__name__)

_QTY_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s?(?:g|gr|kg|ml|cl|l|c\.?\s?à\s?s|c\.?\s?à\s?c|cas|cac|cs|cc|cuill[èe]res?|tbsp|tsp|cups?|oz|lb|tasses?|verres?|sachets?|boîtes?|gousses?|pinc[ée]es?|tranches?)\b",
    re.I,
)
_KEYWORDS = ["ingrédient", "ingredient", "recette", "recipe", "préparation", "preparation", "étape", "step",
             "cuisson", "mélange", "mix", "four", "oven", "minutes", "min ", "portions", "servings", "personnes"]


def caption_has_recipe(caption: Optional[str]) -> bool:
    """Heuristique : la description contient-elle déjà la recette (ingrédients + quantités) ?"""
    if not caption:
        return False
    text = caption.strip()
    low = text.lower()
    qty = len(_QTY_RE.findall(text))
    kw = sum(1 for k in _KEYWORDS if k in low)
    list_lines = sum(1 for ln in text.splitlines() if re.match(r"^\s*(?:[-•*▪️➡️✅🔸🔹]|\d+[.)]|\d+\s?(?:g|ml|cl|kg))", ln.strip()))
    score = 0
    if len(text) >= 150:
        score += 1
    if qty >= 3:
        score += 2
    elif qty >= 1:
        score += 1
    if kw >= 2:
        score += 1
    if list_lines >= 4:
        score += 2
    elif list_lines >= 2:
        score += 1
    return score >= 4


@dataclass
class ImportJob:
    id: str
    request: ImportRequest
    status: str = "queued"      # queued | running | done | error
    step: str = ""
    progress: int = 0
    logs: list[dict[str, str]] = field(default_factory=list)
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    hint: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    local_media_path: Optional[Path] = None

    def log(self, message: str, progress: Optional[int] = None, step: Optional[str] = None) -> None:
        self.logs.append({"time": time.strftime("%H:%M:%S"), "message": message})
        if progress is not None:
            self.progress = progress
        if step is not None:
            self.step = step
        log.info("[job %s] %s", self.id, message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "status": self.status, "step": self.step, "progress": self.progress,
            "logs": self.logs[-80:], "result": self.result, "error": self.error, "hint": self.hint,
            "created_at": self.created_at, "url": self.request.url,
        }


class ImportManager:
    def __init__(self, db: Database):
        self.db = db
        self.jobs: dict[str, ImportJob] = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="import")
        self._lock = threading.Lock()

    def submit(self, req: ImportRequest, local_media_path: Optional[Path] = None) -> ImportJob:
        job = ImportJob(id=new_id(), request=req, local_media_path=local_media_path)
        with self._lock:
            self.jobs[job.id] = job
            # garde au plus 30 jobs en mémoire
            for old in sorted(self.jobs.values(), key=lambda j: j.created_at)[:-30]:
                self.jobs.pop(old.id, None)
        self._executor.submit(self._run, job)
        return job

    def get(self, job_id: str) -> Optional[ImportJob]:
        return self.jobs.get(job_id)

    # ------------------------------------------------------------------

    def _run(self, job: ImportJob) -> None:
        job.status = "running"
        settings = config.load_settings()
        workdir = config.CACHE_DIR / job.id
        workdir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        try:
            draft, analysis = run_import(job, settings, workdir, self.db)
            analysis["elapsed_s"] = round(time.time() - t0, 1)
            job.result = {"recipe": draft.model_dump(mode="json"), "analysis": analysis}
            job.status = "done"
            job.log("Terminé. Vérifiez la recette puis enregistrez-la.", 100, "done")
        except instagram.FetchError as e:
            job.status, job.error, job.hint = "error", e.message, e.hint
            job.log(f"Erreur : {e.message}", step="error")
            for d in e.details:
                job.log(d)
        except OllamaError as e:
            job.status, job.error = "error", str(e)
            job.hint = "Vérifiez qu'Ollama est lancé et que le modèle est installé (menu Réglages)."
            job.log(f"Erreur IA : {e}", step="error")
        except Exception as e:  # noqa: BLE001
            log.error("Import %s : %s\n%s", job.id, e, traceback.format_exc())
            job.status, job.error = "error", f"Erreur inattendue : {e}"
            job.log(f"Erreur inattendue : {e}", step="error")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


def _pick_thumbnail(fetched: Optional[instagram.FetchResult], local_media: Optional[Path]) -> Optional[Image.Image]:
    try:
        if fetched and fetched.thumbnail_path and fetched.thumbnail_path.exists():
            return Image.open(fetched.thumbnail_path)
        if fetched and fetched.image_paths:
            return Image.open(fetched.image_paths[0])
        if fetched and fetched.video_path:
            return media.frame_at(fetched.video_path, 1.0)
        if local_media and local_media.exists():
            if local_media.suffix.lower().lstrip(".") in instagram.IMAGE_EXT:
                return Image.open(local_media)
            return media.frame_at(local_media, 1.0)
    except Exception as e:  # noqa: BLE001
        log.warning("miniature : %s", e)
    return None


def run_import(job: ImportJob, settings: dict[str, Any], workdir: Path, db: Database) -> tuple[Recipe, dict[str, Any]]:
    req = job.request
    fetched: Optional[instagram.FetchResult] = None
    caption = (req.manual_caption or "").strip() or None
    author = (req.manual_author or "").strip() or None
    author_url = None
    source_url = None
    media_type = None
    video_path: Optional[Path] = None
    image_paths: list[Path] = []
    duplicate_of = None

    # 1. Récupération ------------------------------------------------------
    if req.url:
        job.log("Récupération de la publication Instagram…", 5, "fetch")
        fetched = instagram.fetch(req.url, workdir, settings, log_cb=lambda m: job.log(m))
        source_url = fetched.url
        caption = caption or fetched.caption
        author = author or fetched.author
        author_url = fetched.author_url
        media_type = fetched.media_type
        video_path = fetched.video_path
        image_paths = list(fetched.image_paths)
        existing = db.find_by_source_url(source_url)
        if existing:
            duplicate_of = {"id": existing.id, "title": existing.title}
            job.log(f"Cette publication est déjà dans la bibliothèque (« {existing.title} »).")
        job.log(f"Publication récupérée ({fetched.method}, {media_type}).", 20)
    if job.local_media_path and job.local_media_path.exists():
        lp = job.local_media_path
        if lp.suffix.lower().lstrip(".") in instagram.IMAGE_EXT:
            image_paths.append(lp)
            media_type = media_type or "image"
        else:
            video_path = video_path or lp
            media_type = media_type or "video"

    # 2. Analyse locale ----------------------------------------------------
    has_recipe = caption_has_recipe(caption)
    analyze_media = bool(video_path or image_paths) and (
        not has_recipe or settings.get("always_analyze_video") or req.force_video_analysis
    )
    transcript_text: Optional[str] = None
    ocr_text: Optional[str] = None
    transcript_lang = None
    if has_recipe and not analyze_media:
        job.log("La description contient la recette : analyse vidéo ignorée (plus rapide).", 30, "analyze")
    if analyze_media:
        job.log("Analyse locale du média…", 25, "analyze")
        if video_path and settings.get("transcribe_enabled", True):
            info = media.probe(video_path)
            if info.get("has_audio"):
                model_name = settings.get("whisper_model", "small")
                if not transcribe.model_is_downloaded(model_name):
                    job.log(f"Premier lancement : téléchargement du modèle Whisper « {model_name} »…", 28)
                job.log(f"Transcription de l'audio avec Whisper ({model_name})…", 30)
                audio = media.extract_audio(video_path)
                if audio is not None:
                    tr = transcribe.transcribe(audio, model_name)
                    transcript_text = tr.get("text") or None
                    transcript_lang = tr.get("language")
                    job.log(f"Transcription terminée ({len(transcript_text or '')} caractères, langue : {transcript_lang}).", 55)
            else:
                job.log("La vidéo n'a pas de piste audio.", 40)
        if settings.get("ocr_enabled", True):
            frames: list[Image.Image] = []
            if video_path:
                job.log("Extraction des images clés…", 58)
                frames = media.extract_frames(video_path, max_frames=int(settings.get("max_frames", 14)))
            for p in image_paths[:10]:
                try:
                    frames.append(Image.open(p).convert("RGB"))
                except Exception:
                    pass
            if frames:
                job.log(f"Lecture du texte à l'écran sur {len(frames)} image(s) (Vision)…", 60)
                ocr_text = ocr.ocr_frames(frames) or None
                job.log(f"OCR terminé ({len((ocr_text or '').splitlines())} lignes).", 70)

    if not any([caption, transcript_text, ocr_text]):
        raise instagram.FetchError(
            "Aucun contenu exploitable : pas de description, pas de parole détectée et pas de texte à l'écran.",
            "Collez la description de la recette manuellement, ou vérifiez que la vidéo contient bien la recette.",
        )

    # 3. Structuration par l'IA locale --------------------------------------
    client = OllamaClient(settings["ollama_url"], settings["ollama_model"])
    job.log("Connexion à Ollama…", 72, "llm")
    if not client.is_running():
        job.log("Ollama n'est pas lancé, tentative de démarrage…")
        if not client.try_start_server():
            raise OllamaError("Ollama n'est pas lancé. Ouvrez l'application Ollama (ou installez-la depuis ollama.com).")
    if not client.has_model():
        raise OllamaError(f"Le modèle « {settings['ollama_model']} » n'est pas installé. Téléchargez-le dans Réglages.")
    job.log(f"Rédaction de la recette par l'IA locale ({settings['ollama_model']})… cela peut prendre une minute.", 75)
    user_prompt = build_user_prompt(source_url, author, caption, transcript_text, ocr_text, media_type)
    raw = client.chat_json(SYSTEM_PROMPT, user_prompt, LLM_RECIPE_SCHEMA)
    content = RecipeContent.model_validate(raw)
    if not content.ingredients and not content.steps and raw.get("is_recipe", True):
        job.log("Première réponse vide, nouvel essai…")
        raw = client.chat_json(SYSTEM_PROMPT, user_prompt + "\n\nIMPORTANT : la liste d'ingrédients et les étapes ne doivent pas être vides.",
                               LLM_RECIPE_SCHEMA, temperature=0.4)
        content = RecipeContent.model_validate(raw)
    job.log("Recette structurée.", 92, "finalize")

    # 4. Miniature + brouillon ----------------------------------------------
    recipe_id = new_id()
    thumb_name = None
    img = _pick_thumbnail(fetched, job.local_media_path)
    if img is not None:
        try:
            config.ensure_dirs()
            media.save_thumbnail(img, config.IMAGES_DIR / f"{recipe_id}.jpg")
            thumb_name = f"{recipe_id}.jpg"
        except Exception as e:  # noqa: BLE001
            log.warning("miniature non enregistrée : %s", e)

    draft = Recipe(
        **content.model_dump(),
        id=recipe_id,
        source_url=source_url,
        author=author,
        author_url=author_url,
        thumbnail=thumb_name,
        sources=RecipeSources(
            caption=caption, transcript=transcript_text, ocr_text=ocr_text, media_type=media_type,
            used_caption_only=bool(has_recipe and not analyze_media), llm_model=settings["ollama_model"],
            confidence=str(raw.get("confidence") or ""),
        ),
    )
    analysis = {
        "is_recipe": bool(raw.get("is_recipe", True)),
        "confidence": raw.get("confidence"),
        "caption_had_recipe": has_recipe,
        "media_analyzed": analyze_media,
        "media_type": media_type,
        "transcript_chars": len(transcript_text or ""),
        "transcript_language": transcript_lang,
        "ocr_lines": len((ocr_text or "").splitlines()),
        "duplicate_of": duplicate_of,
        "warnings": fetched.warnings if fetched else [],
        "estimated_count": sum(1 for i in content.ingredients if i.estimated),
    }
    return draft, analysis
