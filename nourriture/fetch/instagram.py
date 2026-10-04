"""Récupération d'une publication Instagram (post ou reel).

Stratégie : yt-dlp (gratuit, open source) en premier ; en secours, la page « embed »
publique d'Instagram qui expose la légende et l'image sans connexion.
"""
from __future__ import annotations

import html as html_lib
import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

log = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.4 Safari/605.1.15")
_URL_RE = re.compile(r"instagram\.com/(?:[A-Za-z0-9_.]+/)?(p|reel|reels|tv)/([A-Za-z0-9_-]+)")
VIDEO_EXT = {"mp4", "mov", "m4v", "webm", "mkv"}
IMAGE_EXT = {"jpg", "jpeg", "png", "webp", "heic"}

LogCb = Optional[Callable[[str], None]]


class FetchError(Exception):
    def __init__(self, message: str, hint: str = "", details: Optional[list[str]] = None):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.details = details or []


@dataclass
class FetchResult:
    url: str
    shortcode: Optional[str] = None
    media_type: str = "unknown"          # video | image | carousel | unknown
    caption: Optional[str] = None
    author: Optional[str] = None
    author_url: Optional[str] = None
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    thumbnail_path: Optional[Path] = None
    video_path: Optional[Path] = None
    image_paths: list[Path] = field(default_factory=list)
    duration: Optional[float] = None
    method: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def has_media(self) -> bool:
        return bool(self.video_path or self.image_paths)


def _log(cb: LogCb, msg: str) -> None:
    log.info(msg)
    if cb:
        cb(msg)


# ---------------------------------------------------------------------------
# URL
# ---------------------------------------------------------------------------

def parse_url(url: str) -> tuple[str, str, str]:
    """Renvoie (url canonique, shortcode, type) ou lève FetchError."""
    u = (url or "").strip()
    if not u:
        raise FetchError("Collez un lien Instagram (post ou reel).")
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    if "instagram.com/share/" in u:
        try:
            r = httpx.get(u, headers={"User-Agent": UA}, follow_redirects=True, timeout=20)
            u = str(r.url)
        except Exception as e:
            raise FetchError("Impossible de résoudre ce lien de partage Instagram.", str(e))
    m = _URL_RE.search(u)
    if not m:
        raise FetchError(
            "Ce lien ne ressemble pas à une publication Instagram.",
            "Exemple attendu : https://www.instagram.com/reel/XXXXXXXX/ ou https://www.instagram.com/p/XXXXXXXX/",
        )
    kind, code = m.group(1), m.group(2)
    if kind == "reels":
        kind = "reel"
    return f"https://www.instagram.com/{kind}/{code}/", code, kind


# ---------------------------------------------------------------------------
# Téléchargement générique
# ---------------------------------------------------------------------------

def _download(url: str, dest: Path, log_cb: LogCb = None, timeout: float = 120) -> Optional[Path]:
    try:
        headers = {"User-Agent": UA, "Referer": "https://www.instagram.com/"}
        with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=timeout) as r:
            r.raise_for_status()
            ctype = r.headers.get("content-type", "")
            if dest.suffix == "":
                ext = ".mp4" if "video" in ctype else ".jpg"
                dest = dest.with_suffix(ext)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(65536):
                    f.write(chunk)
        return dest
    except Exception as e:
        _log(log_cb, f"Téléchargement impossible ({e.__class__.__name__}).")
        return None


# ---------------------------------------------------------------------------
# yt-dlp
# ---------------------------------------------------------------------------

class _YDLLogger:
    def __init__(self, cb: LogCb):
        self.cb = cb
        self.errors: list[str] = []

    def debug(self, msg: str) -> None:
        if msg.startswith("[download]") and "%" in msg:
            return
        log.debug("yt-dlp: %s", msg)

    def info(self, msg: str) -> None:
        log.info("yt-dlp: %s", msg)

    def warning(self, msg: str) -> None:
        log.warning("yt-dlp: %s", msg)

    def error(self, msg: str) -> None:
        log.error("yt-dlp: %s", msg)
        self.errors.append(msg)


def _ytdlp_options(workdir: Path, settings: dict[str, Any], logger: _YDLLogger) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": logger,
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "format": "b[ext=mp4]/b/bv*+ba",
        "retries": 2,
        "socket_timeout": 30,
        "writethumbnail": False,
        "noplaylist": False,
        "ignoreerrors": False,
        "overwrites": True,
    }
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    browser = (settings.get("cookies_browser") or "").strip()
    cookies_file = (settings.get("cookies_file") or "").strip()
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    elif cookies_file and Path(cookies_file).expanduser().exists():
        opts["cookiefile"] = str(Path(cookies_file).expanduser())
    return opts


def _fetch_ytdlp(res: FetchResult, workdir: Path, settings: dict[str, Any], log_cb: LogCb) -> None:
    import yt_dlp

    logger = _YDLLogger(log_cb)
    opts = _ytdlp_options(workdir, settings, logger)
    _log(log_cb, "Récupération de la publication avec yt-dlp…")
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(res.url, download=True)
        info = ydl.sanitize_info(info)
    if not info:
        raise RuntimeError("aucune information renvoyée")
    entries = [e for e in (info.get("entries") or [info]) if e]
    first = entries[0] if entries else info
    res.caption = info.get("description") or first.get("description") or res.caption
    res.title = info.get("title") or first.get("title")
    handle = None
    for key in ("channel", "uploader_id", "uploader"):
        val = info.get(key) or first.get(key)
        if val and not str(val).strip("@").isdigit() and " " not in str(val).strip():
            handle = str(val).strip().lstrip("@")
            break
    full_name = info.get("uploader") or first.get("uploader")
    if handle:
        res.author = f"@{handle}"
        res.author_url = f"https://www.instagram.com/{handle}/"
    elif full_name:
        res.author = str(full_name)
    elif info.get("channel_url") or first.get("channel_url"):
        res.author_url = info.get("channel_url") or first.get("channel_url")
    res.thumbnail_url = info.get("thumbnail") or first.get("thumbnail") or res.thumbnail_url
    res.duration = info.get("duration") or first.get("duration")
    for e in entries:
        path: Optional[str] = None
        rd = e.get("requested_downloads") or []
        if rd and rd[0].get("filepath"):
            path = rd[0]["filepath"]
        elif e.get("filepath"):
            path = e["filepath"]
        else:
            try:
                path = ydl.prepare_filename(e)
            except Exception:
                path = None
        if not path or not Path(path).exists():
            continue
        p = Path(path)
        ext = p.suffix.lower().lstrip(".")
        if ext in VIDEO_EXT and res.video_path is None:
            res.video_path = p
        elif ext in IMAGE_EXT:
            res.image_paths.append(p)
    if len(entries) > 1:
        res.media_type = "carousel"
    elif res.video_path:
        res.media_type = "video"
    elif res.image_paths:
        res.media_type = "image"
    res.method = "yt-dlp"


# ---------------------------------------------------------------------------
# Page « embed » publique
# ---------------------------------------------------------------------------

def _strip_tags(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"</p>|</div>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    text = html_lib.unescape(fragment)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _extract_context_json(page: str) -> Optional[dict[str, Any]]:
    m = re.search(r'"contextJSON":"((?:[^"\\]|\\.)*)"', page)
    if not m:
        return None
    try:
        unescaped = json.loads('"' + m.group(1) + '"')
        return json.loads(unescaped)
    except Exception:
        return None


def _fetch_embed(res: FetchResult, workdir: Path, log_cb: LogCb) -> None:
    if not res.shortcode:
        raise RuntimeError("shortcode inconnu")
    _log(log_cb, "Lecture de la page publique Instagram (secours)…")
    url = f"https://www.instagram.com/p/{res.shortcode}/embed/captioned/"
    r = httpx.get(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
                  follow_redirects=True, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}")
    page = r.text
    found_any = False

    ctx = _extract_context_json(page)
    media: Optional[dict[str, Any]] = None
    if ctx:
        try:
            media = ((ctx.get("gql_data") or {}).get("shortcode_media")) or ctx.get("shortcode_media")
        except Exception:
            media = None
    if media:
        found_any = True
        edges = ((media.get("edge_media_to_caption") or {}).get("edges")) or []
        if edges and not res.caption:
            res.caption = (edges[0].get("node") or {}).get("text")
        owner = media.get("owner") or {}
        if owner.get("username") and not res.author:
            res.author = f"@{owner['username']}"
            res.author_url = f"https://www.instagram.com/{owner['username']}/"
        res.thumbnail_url = res.thumbnail_url or media.get("display_url")
        children = ((media.get("edge_sidecar_to_children") or {}).get("edges")) or []
        nodes = [c.get("node") for c in children if c.get("node")] or [media]
        for i, node in enumerate(nodes):
            if not res.has_media or len(nodes) > 1:
                if node.get("is_video") and node.get("video_url") and res.video_path is None:
                    p = _download(node["video_url"], workdir / f"embed_{i}.mp4", log_cb)
                    if p:
                        res.video_path = p
                elif node.get("display_url") and not node.get("is_video"):
                    p = _download(node["display_url"], workdir / f"embed_{i}.jpg", log_cb)
                    if p:
                        res.image_paths.append(p)
        if len(nodes) > 1:
            res.media_type = "carousel"
        elif res.video_path:
            res.media_type = "video"
        elif res.image_paths:
            res.media_type = "image"

    if not res.caption:
        m = re.search(r'<div class="Caption"[^>]*>(.*?)<div class="CaptionComments"', page, re.S)
        if not m:
            m = re.search(r'<div class="Caption"[^>]*>(.*?)</div>', page, re.S)
        if m:
            frag = re.sub(r'<a class="CaptionUsername"[^>]*>.*?</a>', "", m.group(1), flags=re.S)
            cap = _strip_tags(frag)
            if cap:
                res.caption = cap
                found_any = True
    if not res.author:
        m = re.search(r'class="(?:CaptionUsername|UsernameText)"[^>]*>(.*?)</a>', page, re.S)
        if m:
            name = _strip_tags(m.group(1)).strip()
            if name:
                res.author = f"@{name.lstrip('@')}"
                res.author_url = f"https://www.instagram.com/{name.lstrip('@')}/"
                found_any = True
    if not res.thumbnail_url:
        m = re.search(r'class="EmbeddedMediaImage"[^>]*src="([^"]+)"', page)
        if m:
            res.thumbnail_url = html_lib.unescape(m.group(1))
            found_any = True
    if not res.video_path and not res.image_paths:
        m = re.search(r'"video_url":"((?:[^"\\]|\\.)*)"', page)
        if m:
            try:
                vurl = json.loads('"' + m.group(1) + '"')
                p = _download(vurl, workdir / "embed_video.mp4", log_cb)
                if p:
                    res.video_path = p
                    res.media_type = "video"
                    found_any = True
            except Exception:
                pass
        elif res.thumbnail_url:
            p = _download(res.thumbnail_url, workdir / "embed_image.jpg", log_cb)
            if p:
                res.image_paths.append(p)
                res.media_type = res.media_type if res.media_type != "unknown" else "image"
                found_any = True
    if not found_any:
        if "login" in page.lower() and "Caption" not in page:
            raise RuntimeError("Instagram demande une connexion")
        raise RuntimeError("page vide ou format inconnu")
    res.method = res.method or "embed"


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def _hint_for(errors: list[str]) -> str:
    joined = " ".join(errors).lower()
    if "private" in joined or "privé" in joined:
        return "Cette publication semble privée : seules les publications publiques peuvent être importées."
    if any(k in joined for k in ("login", "rate-limit", "rate limit", "429", "please wait", "not available", "connexion", "401", "403")):
        return ("Instagram limite les accès anonymes. Dans Réglages, indiquez un navigateur où vous êtes connecté à "
                "Instagram (Firefox ou Chrome) pour utiliser ses cookies, ou collez la description manuellement.")
    return "Vérifiez le lien et votre connexion internet, ou collez la description manuellement."


def fetch(url: str, workdir: Path, settings: dict[str, Any], log_cb: LogCb = None) -> FetchResult:
    canonical, code, _kind = parse_url(url)
    workdir.mkdir(parents=True, exist_ok=True)
    res = FetchResult(url=canonical, shortcode=code)
    errors: list[str] = []
    try:
        _fetch_ytdlp(res, workdir, settings, log_cb)
    except Exception as e:  # noqa: BLE001
        msg = str(e).replace("ERROR: ", "").strip()
        log.warning("yt-dlp a échoué : %s", msg)
        errors.append(f"yt-dlp : {msg[:300]}")
    if not res.caption or not res.has_media:
        try:
            _fetch_embed(res, workdir, log_cb)
        except Exception as e:  # noqa: BLE001
            log.warning("embed a échoué : %s", e)
            errors.append(f"page publique : {str(e)[:300]}")
    if res.thumbnail_url and not res.thumbnail_path:
        res.thumbnail_path = _download(res.thumbnail_url, workdir / "thumbnail.jpg", log_cb)
    if not res.caption and not res.has_media:
        raise FetchError("Impossible de récupérer cette publication Instagram.", _hint_for(errors), errors)
    if errors:
        res.warnings.extend(errors)
    if res.caption:
        res.caption = res.caption.strip()
    return res
