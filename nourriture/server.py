"""API locale (FastAPI) servie sur 127.0.0.1 et interface web embarquée."""
from __future__ import annotations

import base64
import io
import json
import logging
import shutil
import subprocess
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

from . import __version__, config
from .analyze import media, transcribe
from .db import Database
from .llm.ollama import OllamaClient, ollama_app_installed
from .menu import generate_menu, menu_as_text, reroll_slot, shopping_list
from .models import (CATEGORIES, PROTEINS, ImportRequest, Menu, MenuGenerateRequest, Recipe, RecipeContent,
                     new_id, now_iso)
from .pipeline import ImportManager

log = logging.getLogger(__name__)

EXPORT_FORMAT_VERSION = 1


# ---------------------------------------------------------------------------
# Tâches génériques (téléchargements de modèles)
# ---------------------------------------------------------------------------

class TaskManager:
    def __init__(self) -> None:
        self.tasks: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start(self, kind: str, target, *args) -> dict[str, Any]:
        task = {"id": uuid.uuid4().hex[:10], "kind": kind, "status": "running", "progress": 0, "message": "", "error": None,
                "created_at": now_iso()}
        with self._lock:
            self.tasks[task["id"]] = task

        def runner() -> None:
            try:
                target(task, *args)
                task["status"] = "done"
                task["progress"] = 100
            except Exception as e:  # noqa: BLE001
                log.exception("tâche %s", kind)
                task["status"] = "error"
                task["error"] = str(e)

        threading.Thread(target=runner, daemon=True, name=f"task-{kind}").start()
        return task

    def get(self, task_id: str) -> Optional[dict[str, Any]]:
        return self.tasks.get(task_id)

    def running(self, kind: str) -> Optional[dict[str, Any]]:
        return next((t for t in self.tasks.values() if t["kind"] == kind and t["status"] == "running"), None)


def _pull_ollama_model(task: dict[str, Any], base_url: str, name: str) -> None:
    client = OllamaClient(base_url)
    if not client.is_running() and not client.try_start_server():
        raise RuntimeError("Ollama n'est pas lancé.")
    task["message"] = f"Téléchargement de {name}…"
    for line in client.pull_model(name):
        status = line.get("status", "")
        total, done = line.get("total"), line.get("completed")
        if total and done:
            task["progress"] = int(done * 100 / total)
            task["message"] = f"{status} — {done / 1e9:.1f} / {total / 1e9:.1f} Go"
        elif status:
            task["message"] = status
        if line.get("error"):
            raise RuntimeError(line["error"])


def _download_whisper(task: dict[str, Any], name: str) -> None:
    task["message"] = f"Téléchargement du modèle Whisper « {name} »…"
    transcribe.download_model(name)
    task["message"] = "Modèle Whisper prêt."


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

def create_app(db: Optional[Database] = None) -> FastAPI:
    config.ensure_dirs()
    db = db or Database(config.DB_PATH)
    importer = ImportManager(db)
    tasks = TaskManager()
    app = FastAPI(title="Nourriture", version=__version__, docs_url=None, redoc_url=None)
    app.state.db = db
    app.state.importer = importer

    def _recipe_summary(r: Recipe) -> dict[str, Any]:
        d = r.model_dump(mode="json")
        d.pop("sources", None)
        d["total_time_min"] = r.total_time_min
        d["estimated_count"] = sum(1 for i in r.ingredients if i.estimated)
        return d

    def _recipe_full(r: Recipe) -> dict[str, Any]:
        d = r.model_dump(mode="json")
        d["total_time_min"] = r.total_time_min
        return d

    def _settings_client() -> tuple[dict[str, Any], OllamaClient]:
        s = config.load_settings()
        return s, OllamaClient(s["ollama_url"], s["ollama_model"])

    # ------------------------------------------------------------- santé & réglages

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        s, client = _settings_client()
        running = client.is_running()
        return {
            "ok": True,
            "version": __version__,
            "data_dir": str(config.DATA_DIR),
            "counts": {"recipes": db.count_recipes(), "menus": len(db.list_menus(limit=1000))},
            "ollama": {
                "running": running,
                "version": client.version() if running else None,
                "app_installed": ollama_app_installed(),
                "model": s["ollama_model"],
                "has_model": client.has_model() if running else False,
                "models": [m.get("name") for m in client.list_models()] if running else [],
                "pulling": tasks.running("ollama_pull"),
            },
            "whisper": {
                "model": s["whisper_model"],
                "downloaded": transcribe.model_is_downloaded(s["whisper_model"]),
                "downloading": tasks.running("whisper_download"),
            },
            "categories": CATEGORIES,
            "proteins": PROTEINS,
        }

    @app.get("/api/settings")
    def get_settings() -> dict[str, Any]:
        return {
            "settings": config.load_settings(),
            "whisper_models": config.WHISPER_MODELS,
            "recommended_llm_models": config.RECOMMENDED_LLM_MODELS,
            "cookie_browsers": config.COOKIE_BROWSERS,
            "data_dir": str(config.DATA_DIR),
        }

    @app.put("/api/settings")
    def put_settings(update: dict[str, Any] = Body(...)) -> dict[str, Any]:
        return {"settings": config.save_settings(update)}

    @app.post("/api/ollama/start")
    def ollama_start() -> dict[str, Any]:
        _, client = _settings_client()
        ok = client.try_start_server()
        return {"running": ok, "app_installed": ollama_app_installed()}

    @app.post("/api/ollama/pull")
    def ollama_pull(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        name = (payload.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "Nom de modèle manquant.")
        existing = tasks.running("ollama_pull")
        if existing:
            return {"task": existing}
        s, _ = _settings_client()
        return {"task": tasks.start("ollama_pull", _pull_ollama_model, s["ollama_url"], name)}

    @app.post("/api/whisper/download")
    def whisper_download(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        name = (payload.get("name") or config.load_settings()["whisper_model"]).strip()
        if name not in config.WHISPER_MODELS:
            raise HTTPException(400, "Modèle Whisper inconnu.")
        existing = tasks.running("whisper_download")
        if existing:
            return {"task": existing}
        return {"task": tasks.start("whisper_download", _download_whisper, name)}

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        t = tasks.get(task_id)
        if not t:
            raise HTTPException(404, "Tâche inconnue.")
        return t

    @app.post("/api/system/open-url")
    def open_url(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        url = str(payload.get("url") or "")
        if not url.startswith(("http://", "https://")):
            raise HTTPException(400, "URL invalide.")
        webbrowser.open(url)
        return {"ok": True}

    @app.post("/api/system/reveal")
    def reveal(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        what = payload.get("what", "data")
        target = {"data": config.DATA_DIR, "logs": config.LOG_DIR, "images": config.IMAGES_DIR}.get(what, config.DATA_DIR)
        path = payload.get("path")
        if path and Path(path).exists():
            subprocess.run(["open", "-R", str(path)], check=False)
        else:
            subprocess.run(["open", str(target)], check=False)
        return {"ok": True}

    # ------------------------------------------------------------- import

    @app.post("/api/import")
    def start_import(req: ImportRequest) -> dict[str, Any]:
        if not (req.url or (req.manual_caption or "").strip()):
            raise HTTPException(400, "Indiquez un lien Instagram ou collez une description.")
        job = importer.submit(req)
        return {"job": job.to_dict()}

    @app.post("/api/import/upload")
    async def start_import_upload(
        file: UploadFile = File(...),
        url: str = Form(""),
        manual_caption: str = Form(""),
        manual_author: str = Form(""),
        force_video_analysis: bool = Form(False),
    ) -> dict[str, Any]:
        suffix = Path(file.filename or "media").suffix.lower() or ".mp4"
        dest = config.CACHE_DIR / "uploads" / f"{new_id()}{suffix}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        req = ImportRequest(url=url or None, manual_caption=manual_caption or None, manual_author=manual_author or None,
                            force_video_analysis=force_video_analysis)
        job = importer.submit(req, local_media_path=dest)
        return {"job": job.to_dict()}

    @app.get("/api/import/{job_id}")
    def get_import(job_id: str) -> dict[str, Any]:
        job = importer.get(job_id)
        if not job:
            raise HTTPException(404, "Import inconnu.")
        return {"job": job.to_dict()}

    # ------------------------------------------------------------- recettes

    @app.get("/api/recipes")
    def list_recipes(
        q: str = "", category: str = "", tags: str = "", max_time: Optional[int] = None,
        favorites: bool = False, sort: str = "recent",
    ) -> dict[str, Any]:
        tag_list = [t for t in tags.split(",") if t.strip()]
        recipes = db.list_recipes(query=q, category=category or None, tags=tag_list or None,
                                  max_total_time=max_time, favorites_only=favorites, sort=sort)
        return {"recipes": [_recipe_summary(r) for r in recipes], "total": db.count_recipes()}

    @app.get("/api/recipes/facets")
    def facets() -> dict[str, Any]:
        return {"tags": db.tag_counts(), "categories": db.category_counts(), "total": db.count_recipes()}

    @app.post("/api/recipes")
    def create_recipe(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        recipe = Recipe.model_validate(payload)
        if db.get_recipe(recipe.id):
            recipe.id = new_id()
        recipe.created_at = now_iso()
        db.upsert_recipe(recipe)
        return {"recipe": _recipe_full(recipe)}

    @app.get("/api/recipes/{recipe_id}")
    def get_recipe(recipe_id: str) -> dict[str, Any]:
        r = db.get_recipe(recipe_id)
        if not r:
            raise HTTPException(404, "Recette introuvable.")
        return {"recipe": _recipe_full(r)}

    @app.put("/api/recipes/{recipe_id}")
    def update_recipe(recipe_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        existing = db.get_recipe(recipe_id)
        if not existing:
            raise HTTPException(404, "Recette introuvable.")
        merged = {**existing.model_dump(mode="json"), **payload, "id": recipe_id, "created_at": existing.created_at}
        recipe = Recipe.model_validate(merged)
        db.upsert_recipe(recipe)
        return {"recipe": _recipe_full(recipe)}

    @app.delete("/api/recipes/{recipe_id}")
    def delete_recipe(recipe_id: str) -> dict[str, Any]:
        r = db.get_recipe(recipe_id)
        if not r:
            raise HTTPException(404, "Recette introuvable.")
        db.delete_recipe(recipe_id)
        if r.thumbnail:
            try:
                (config.IMAGES_DIR / r.thumbnail).unlink(missing_ok=True)
            except OSError:
                pass
        return {"ok": True}

    @app.post("/api/recipes/{recipe_id}/favorite")
    def toggle_favorite(recipe_id: str) -> dict[str, Any]:
        r = db.get_recipe(recipe_id)
        if not r:
            raise HTTPException(404, "Recette introuvable.")
        r.favorite = not r.favorite
        db.upsert_recipe(r)
        return {"recipe": _recipe_full(r)}

    @app.post("/api/recipes/{recipe_id}/thumbnail")
    async def set_thumbnail(recipe_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
        r = db.get_recipe(recipe_id)
        if not r:
            raise HTTPException(404, "Recette introuvable.")
        data = await file.read()
        try:
            img = Image.open(io.BytesIO(data))
        except Exception:
            raise HTTPException(400, "Image illisible.")
        name = f"{recipe_id}-{int(time.time())}.jpg"
        media.save_thumbnail(img, config.IMAGES_DIR / name)
        if r.thumbnail and r.thumbnail != name:
            (config.IMAGES_DIR / r.thumbnail).unlink(missing_ok=True)
        r.thumbnail = name
        db.upsert_recipe(r)
        return {"recipe": _recipe_full(r)}

    @app.post("/api/drafts/{draft_id}/thumbnail")
    async def set_draft_thumbnail(draft_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
        """Miniature pour un brouillon pas encore enregistré."""
        data = await file.read()
        try:
            img = Image.open(io.BytesIO(data))
        except Exception:
            raise HTTPException(400, "Image illisible.")
        name = f"{draft_id}-{int(time.time())}.jpg"
        media.save_thumbnail(img, config.IMAGES_DIR / name)
        return {"thumbnail": name}

    # ------------------------------------------------------------- export / import JSON

    def _export_payload(recipes: list[Recipe], with_images: bool = True) -> dict[str, Any]:
        items = []
        for r in recipes:
            d = r.model_dump(mode="json")
            if with_images and r.thumbnail:
                p = config.IMAGES_DIR / r.thumbnail
                if p.exists():
                    d["thumbnail_data"] = "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()
            items.append(d)
        return {"app": "nourriture", "format": EXPORT_FORMAT_VERSION, "exported_at": now_iso(), "recipes": items}

    @app.get("/api/export")
    def export_json(ids: str = "", images: bool = True) -> Response:
        id_list = [i for i in ids.split(",") if i.strip()]
        recipes = list(db.get_recipes(id_list).values()) if id_list else db.all_recipes()
        payload = _export_payload(recipes, with_images=images)
        fname = f"nourriture-recettes-{datetime.now():%Y-%m-%d}.json"
        return Response(json.dumps(payload, ensure_ascii=False, indent=1), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{fname}"'})

    @app.post("/api/export/save")
    def export_save(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        id_list = payload.get("ids") or []
        recipes = list(db.get_recipes(id_list).values()) if id_list else db.all_recipes()
        data = _export_payload(recipes, with_images=payload.get("images", True))
        downloads = Path.home() / "Downloads"
        downloads.mkdir(exist_ok=True)
        fname = downloads / f"nourriture-recettes-{datetime.now():%Y-%m-%d-%H%M}.json"
        fname.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        subprocess.run(["open", "-R", str(fname)], check=False)
        return {"path": str(fname), "count": len(recipes)}

    @app.post("/api/import-json")
    async def import_json(file: UploadFile = File(...), mode: str = Form("skip")) -> dict[str, Any]:
        try:
            data = json.loads((await file.read()).decode("utf-8"))
        except Exception:
            raise HTTPException(400, "Fichier JSON illisible.")
        items = data.get("recipes") if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise HTTPException(400, "Format inattendu : il faut une liste de recettes.")
        imported = updated = skipped = errors = 0
        for raw in items:
            try:
                thumb_data = raw.pop("thumbnail_data", None) if isinstance(raw, dict) else None
                incoming = Recipe.model_validate(raw)
            except Exception:
                errors += 1
                continue
            existing = db.find_by_source_url(incoming.source_url) if incoming.source_url else None
            if existing is None and db.get_recipe(incoming.id):
                existing = db.get_recipe(incoming.id)
            if existing and mode == "skip":
                skipped += 1
                continue
            if existing:
                incoming.id = existing.id
                incoming.created_at = existing.created_at
                updated += 1
            else:
                if db.get_recipe(incoming.id):
                    incoming.id = new_id()
                imported += 1
            # miniature
            if thumb_data and thumb_data.startswith("data:image"):
                try:
                    b = base64.b64decode(thumb_data.split(",", 1)[1])
                    name = f"{incoming.id}.jpg"
                    media.save_thumbnail(Image.open(io.BytesIO(b)), config.IMAGES_DIR / name)
                    incoming.thumbnail = name
                except Exception:
                    incoming.thumbnail = None
            elif incoming.thumbnail and not (config.IMAGES_DIR / incoming.thumbnail).exists():
                incoming.thumbnail = None
            db.upsert_recipe(incoming)
        return {"imported": imported, "updated": updated, "skipped": skipped, "errors": errors}

    # ------------------------------------------------------------- menus

    def _menu_payload(menu: Menu) -> dict[str, Any]:
        recipes = db.get_recipes([s.recipe_id for s in menu.slots if s.recipe_id])
        return {
            "menu": menu.model_dump(mode="json"),
            "recipes": {rid: _recipe_summary(r) for rid, r in recipes.items()},
            "shopping_list": shopping_list(db, menu),
        }

    @app.post("/api/menus/generate")
    def menus_generate(req: MenuGenerateRequest) -> dict[str, Any]:
        try:
            menu, warnings = generate_menu(db, req)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {**_menu_payload(menu), "warnings": warnings}

    @app.post("/api/menus/reroll")
    def menus_reroll(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        menu = Menu.model_validate(payload.get("menu") or {})
        try:
            menu = reroll_slot(db, menu, int(payload.get("slot_index", 0)))
        except ValueError as e:
            raise HTTPException(400, str(e))
        if db.get_menu(menu.id):
            db.save_menu(menu)
        return _menu_payload(menu)

    @app.post("/api/menus/preview")
    def menus_preview(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        menu = Menu.model_validate(payload.get("menu") or {})
        return _menu_payload(menu)

    @app.get("/api/menus")
    def menus_list() -> dict[str, Any]:
        menus = db.list_menus()
        out = []
        for m in menus:
            recipes = db.get_recipes([s.recipe_id for s in m.slots if s.recipe_id])
            out.append({"menu": m.model_dump(mode="json"),
                        "titles": [recipes[s.recipe_id].title if s.recipe_id in recipes else None for s in m.slots]})
        return {"menus": out}

    @app.get("/api/menus/{menu_id}")
    def menus_get(menu_id: str) -> dict[str, Any]:
        m = db.get_menu(menu_id)
        if not m:
            raise HTTPException(404, "Menu introuvable.")
        return _menu_payload(m)

    @app.put("/api/menus/{menu_id}")
    def menus_save(menu_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        menu = Menu.model_validate({**(payload.get("menu") or payload), "id": menu_id})
        db.save_menu(menu)
        return _menu_payload(menu)

    @app.delete("/api/menus/{menu_id}")
    def menus_delete(menu_id: str) -> dict[str, Any]:
        if not db.delete_menu(menu_id):
            raise HTTPException(404, "Menu introuvable.")
        return {"ok": True}

    @app.get("/api/menus/{menu_id}/text", response_class=PlainTextResponse)
    def menus_text(menu_id: str) -> str:
        m = db.get_menu(menu_id)
        if not m:
            raise HTTPException(404, "Menu introuvable.")
        return menu_as_text(db, m)

    @app.post("/api/menus/text", response_class=PlainTextResponse)
    def menus_text_preview(payload: dict[str, Any] = Body(...)) -> str:
        return menu_as_text(db, Menu.model_validate(payload.get("menu") or {}))

    # ------------------------------------------------------------- fichiers statiques

    @app.get("/images/{name}")
    def image(name: str) -> FileResponse:
        if "/" in name or ".." in name:
            raise HTTPException(400)
        p = config.IMAGES_DIR / name
        if not p.exists():
            raise HTTPException(404)
        return FileResponse(p, headers={"Cache-Control": "max-age=86400"})

    static_dir = config.resource_path("static")
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    return app
