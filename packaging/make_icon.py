"""Génère l'icône de l'application (PNG pour l'interface, .icns pour le bundle macOS).

Usage : python packaging/make_icon.py
Produit : nourriture/static/icon.png et packaging/Nourriture.icns (via iconutil, fourni par macOS).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent


def rounded_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return m


def render(size: int = 1024) -> Image.Image:
    # Fond : dégradé chaud (tomate → abricot) dans un carré arrondi façon macOS.
    img = Image.new("RGB", (size, size))
    top, bottom = (232, 92, 52), (248, 168, 86)
    px = img.load()
    for y in range(size):
        t = y / (size - 1)
        row = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(size):
            px[x, y] = row
    # Léger reflet
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-size * 0.2, -size * 0.55, size * 1.2, size * 0.55), fill=(255, 255, 255, 38))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    # Emoji marmite rendu avec la police Apple Color Emoji
    emoji_drawn = False
    for font_size in (160, 128, 96, 64):
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", font_size)
            layer = Image.new("RGBA", (font_size * 2, font_size * 2), (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((font_size // 2, font_size // 2), "🍲", font=font, embedded_color=True)
            bbox = layer.getbbox()
            if not bbox:
                continue
            glyph = layer.crop(bbox)
            target = int(size * 0.66)
            glyph = glyph.resize((target, int(glyph.height * target / glyph.width)), Image.LANCZOS)
            img.alpha_composite(glyph, ((size - glyph.width) // 2, (size - glyph.height) // 2 + int(size * 0.02)))
            emoji_drawn = True
            break
        except Exception:
            continue
    if not emoji_drawn:  # repli : une marmite stylisée en formes simples
        d = ImageDraw.Draw(img)
        c = size // 2
        d.rounded_rectangle((c - 300, c - 60, c + 300, c + 280), radius=90, fill=(70, 40, 30, 255))
        d.rounded_rectangle((c - 330, c - 110, c + 330, c - 40, ), radius=35, fill=(245, 235, 220, 255))
        d.ellipse((c - 40, c - 180, c + 40, c - 100), fill=(245, 235, 220, 255))
    # Masque arrondi (ratio macOS ≈ 22,37 % du côté)
    mask = rounded_mask(size, int(size * 0.2237))
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    # Marge transparente macOS (l'icône occupe ~82 % du canevas)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inner = int(size * 0.82)
    canvas.alpha_composite(out.resize((inner, inner), Image.LANCZOS), ((size - inner) // 2, (size - inner) // 2))
    return canvas


def main() -> None:
    icon = render(1024)
    static_png = ROOT / "nourriture" / "static" / "icon.png"
    icon.resize((256, 256), Image.LANCZOS).save(static_png)
    print("écrit", static_png)
    icns = ROOT / "packaging" / "Nourriture.icns"
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "Nourriture.iconset"
        iconset.mkdir()
        for s in (16, 32, 128, 256, 512):
            icon.resize((s, s), Image.LANCZOS).save(iconset / f"icon_{s}x{s}.png")
            icon.resize((s * 2, s * 2), Image.LANCZOS).save(iconset / f"icon_{s}x{s}@2x.png")
        if shutil.which("iconutil"):
            subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True)
            print("écrit", icns)
        else:
            print("iconutil introuvable : .icns non généré", file=sys.stderr)


if __name__ == "__main__":
    main()
