"""Fabrique une fausse « reel » (vidéo verticale avec texte à l'écran + voix) pour tester la chaîne sans Instagram.

Usage : python tests/make_sample_video.py sortie.mp4 [audio.aiff]
Sans fichier audio, la voix est générée avec la commande macOS `say`.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

TEXT = ("Bonjour à tous, aujourd'hui on prépare un poulet au curry rapide. Il vous faut deux blancs de poulet, "
        "une boîte de lait de coco, un oignon, deux cuillères à soupe de pâte de curry et un peu de coriandre. "
        "Faites revenir l'oignon, ajoutez le poulet coupé en morceaux, puis la pâte de curry et le lait de coco. "
        "Laissez mijoter quinze minutes et servez avec du riz.")

SLIDES = [
    ["POULET CURRY", "EXPRESS 🍛", "", "15 MIN"],
    ["INGRÉDIENTS", "2 blancs de poulet", "400 ml lait de coco", "1 oignon", "2 c. à s. pâte de curry", "coriandre"],
    ["1. Faire revenir l'oignon", "2. Ajouter le poulet", "3. Pâte de curry + lait de coco", "4. Mijoter 15 min"],
    ["Bon appétit !", "", "@chef_test"],
]


def render_slide(lines: list[str], w: int, h: int, bg: tuple[int, int, int]) -> np.ndarray:
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 54)
    except OSError:
        font = ImageFont.load_default()
    y = h // 2 - len(lines) * 40
    for line in lines:
        bbox = d.textbbox((0, 0), line, font=font)
        d.text(((w - (bbox[2] - bbox[0])) // 2, y), line, fill=(255, 255, 255), font=font)
        y += 80
    return np.asarray(img)


def main(out: str, audio: str | None = None) -> None:
    out_path = Path(out)
    if audio is None:
        tmp = Path(tempfile.mkdtemp()) / "voice.aiff"
        subprocess.run(["say", "-v", "Thomas", "-o", str(tmp), TEXT], check=True)
        audio = str(tmp)
    w, h, fps = 720, 1280, 24
    with av.open(audio) as ac:
        astream_in = ac.streams.audio[0]
        duration = float(ac.duration / av.time_base) if ac.duration else 20.0
        a_frames = list(ac.decode(astream_in))
    total_frames = int(duration * fps) + fps
    colors = [(120, 50, 30), (30, 80, 60), (40, 40, 110), (100, 30, 90)]
    with av.open(str(out_path), "w") as oc:
        try:
            vs = oc.add_stream("libx264", rate=fps)
        except Exception:
            vs = oc.add_stream("mpeg4", rate=fps)
        vs.width, vs.height, vs.pix_fmt = w, h, "yuv420p"
        a_out = oc.add_stream("aac", rate=astream_in.rate)
        a_out.layout = "mono"
        slides = [render_slide(s, w, h, colors[i]) for i, s in enumerate(SLIDES)]
        per = total_frames // len(slides) + 1
        for i in range(total_frames):
            frame = av.VideoFrame.from_ndarray(slides[min(i // per, len(slides) - 1)], format="rgb24")
            for pkt in vs.encode(frame):
                oc.mux(pkt)
        for pkt in vs.encode():
            oc.mux(pkt)
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=astream_in.rate)
        for fr in a_frames:
            for rf in resampler.resample(fr):
                rf.pts = None
                for pkt in a_out.encode(rf):
                    oc.mux(pkt)
        for pkt in a_out.encode():
            oc.mux(pkt)
    print("écrit", out_path, f"({duration:.1f}s)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
