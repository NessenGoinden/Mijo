"""Point d'entrée : serveur local + fenêtre native macOS (pywebview)."""
from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import threading
import time
import webbrowser

import httpx

from . import APP_NAME, __version__, config

log = logging.getLogger(__name__)


def _free_port(preferred: int = 8765) -> int:
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("Aucun port libre")


def _start_server(port: int):
    import uvicorn

    from .server import create_app

    app = create_app()
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(cfg)
    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=1).status_code == 200:
                return server
        except Exception:
            pass
        time.sleep(0.15)
    raise RuntimeError("Le serveur local n'a pas démarré.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nourriture", description="Nourriture — recettes Instagram en local")
    parser.add_argument("--browser", action="store_true", help="ouvrir dans le navigateur au lieu d'une fenêtre native")
    parser.add_argument("--port", type=int, default=int(os.environ.get("NOURRITURE_PORT", 8765)))
    parser.add_argument("--no-open", action="store_true", help="ne pas ouvrir de fenêtre (mode serveur)")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    args = parser.parse_args(argv)

    config.setup_logging(logging.DEBUG if os.environ.get("NOURRITURE_DEBUG") else logging.INFO)
    config.ensure_dirs()
    port = _free_port(args.port)
    log.info("%s %s — données : %s", APP_NAME, __version__, config.DATA_DIR)
    server = _start_server(port)
    url = f"http://127.0.0.1:{port}/"
    if sys.stdout:
        print(f"{APP_NAME} : {url}", flush=True)

    if args.no_open or args.browser:
        if args.browser:
            webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        server.should_exit = True
        return 0

    import webview

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    window = webview.create_window(
        APP_NAME, url, width=1240, height=820, min_size=(900, 600), text_select=True,
    )

    def on_closed() -> None:
        server.should_exit = True

    window.events.closed += on_closed
    webview.start(private_mode=False, storage_path=str(config.DATA_DIR / "webview"))
    server.should_exit = True
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
