"""Diagonal watermark for free-plan PNGs (tile cached, fast)."""
from __future__ import annotations
import io
import os
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


@lru_cache(maxsize=8)
def _tile(text: str, size: int):
    try:
        font = ImageFont.truetype(FONT, size)
    except Exception:
        font = ImageFont.load_default()
    w = int(font.getlength(text)) + size * 4
    t = Image.new("RGBA", (w, size * 6), (0, 0, 0, 0))
    ImageDraw.Draw(t).text((size, size), text, fill=(31, 111, 235, 40), font=font)
    return t.rotate(25, expand=True, resample=Image.BICUBIC)


def apply(png: bytes, text=None) -> bytes:
    text = text or f"CivilBot Free  •  t.me/{os.getenv('BOT_USERNAME', 'CivilBot')}"
    try:
        im = Image.open(io.BytesIO(png)).convert("RGBA")
    except Exception:
        return png
    w, h = im.size
    tile = _tile(text, max(14, w // 30))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tw, th = tile.size
    for y in range(-th // 2, h, int(th * 0.9)):
        off = (y // max(1, int(th * 0.9)) % 2) * tw // 2
        for x in range(-tw + off, w, tw):
            layer.alpha_composite(tile, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))
    out = Image.alpha_composite(im, layer).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG", compress_level=3)
    return buf.getvalue()
