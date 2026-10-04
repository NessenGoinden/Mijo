"""Client minimal pour l'API HTTP locale d'Ollama (gratuit, tourne sur le Mac)."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

import httpx

log = logging.getLogger(__name__)

OLLAMA_APP_PATHS = [
    Path("/Applications/Ollama.app"),
    Path.home() / "Applications" / "Ollama.app",
]


class OllamaError(Exception):
    pass


def find_ollama_binary() -> Optional[str]:
    exe = shutil.which("ollama")
    if exe:
        return exe
    for app in OLLAMA_APP_PATHS:
        cand = app / "Contents" / "Resources" / "ollama"
        if cand.exists():
            return str(cand)
    for cand in ("/usr/local/bin/ollama", "/opt/homebrew/bin/ollama"):
        if Path(cand).exists():
            return cand
    return None


def ollama_app_installed() -> bool:
    return any(p.exists() for p in OLLAMA_APP_PATHS) or find_ollama_binary() is not None


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen2.5:7b"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    # ------------------------------------------------------------- état

    def version(self, timeout: float = 2.0) -> Optional[str]:
        try:
            r = httpx.get(f"{self.base_url}/api/version", timeout=timeout)
            r.raise_for_status()
            return r.json().get("version")
        except Exception:
            return None

    def is_running(self) -> bool:
        return self.version() is not None

    def list_models(self) -> list[dict[str, Any]]:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            return r.json().get("models", [])
        except Exception:
            return []

    def has_model(self, name: Optional[str] = None) -> bool:
        name = name or self.model
        names = {m.get("name", "") for m in self.list_models()}
        return name in names or f"{name}:latest" in names or name.split(":")[0] + ":latest" in names and ":" not in name

    def try_start_server(self, wait_seconds: float = 25.0) -> bool:
        """Lance Ollama s'il est installé mais pas démarré."""
        if self.is_running():
            return True
        started = False
        for app in OLLAMA_APP_PATHS:
            if app.exists():
                try:
                    subprocess.Popen(["open", "-g", "-a", str(app)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    started = True
                    break
                except Exception as e:  # pragma: no cover
                    log.warning("open -a Ollama a échoué : %s", e)
        if not started:
            exe = find_ollama_binary()
            if exe:
                try:
                    subprocess.Popen(
                        [exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        env={**os.environ, "OLLAMA_HOST": "127.0.0.1:11434"}, start_new_session=True,
                    )
                    started = True
                except Exception as e:  # pragma: no cover
                    log.warning("ollama serve a échoué : %s", e)
        if not started:
            return False
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if self.is_running():
                return True
            time.sleep(0.5)
        return False

    # ------------------------------------------------------------- modèles

    def pull_model(self, name: str) -> Iterator[dict[str, Any]]:
        """Télécharge un modèle ; renvoie les lignes de progression du flux."""
        with httpx.stream("POST", f"{self.base_url}/api/pull", json={"name": name, "stream": True}, timeout=None) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def delete_model(self, name: str) -> bool:
        try:
            r = httpx.request("DELETE", f"{self.base_url}/api/delete", json={"name": name}, timeout=30)
            return r.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------- génération

    def chat_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        temperature: float = 0.2,
        timeout: float = 900.0,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        model = model or self.model
        approx_tokens = (len(system) + len(user)) // 3 + 1800
        num_ctx = int(min(16384, max(4096, approx_tokens * 1.3)))
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": schema,
            "keep_alive": "15m",
            "options": {"temperature": temperature, "num_ctx": num_ctx, "num_predict": 4096},
        }
        t0 = time.time()
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=timeout)
        except httpx.ConnectError as e:
            raise OllamaError("Impossible de joindre Ollama. Lancez l'application Ollama puis réessayez.") from e
        except httpx.TimeoutException as e:
            raise OllamaError("Ollama met trop de temps à répondre (modèle trop lourd pour ce Mac ?).") from e
        if r.status_code == 404:
            raise OllamaError(f"Le modèle « {model} » n'est pas installé dans Ollama. Téléchargez-le dans les Réglages.")
        if r.status_code >= 400:
            raise OllamaError(f"Erreur Ollama ({r.status_code}) : {r.text[:300]}")
        data = r.json()
        content = (data.get("message") or {}).get("content", "")
        log.info("Ollama %s a répondu en %.1fs (%s tokens)", model, time.time() - t0, data.get("eval_count"))
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start, end = content.find("{"), content.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    pass
            raise OllamaError("Le modèle n'a pas renvoyé un JSON valide. Réessayez ou changez de modèle.")
