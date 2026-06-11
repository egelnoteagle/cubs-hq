"""Pillow helpers for rendering onto the 64x64 panel.

Small, dependency-light building blocks the display modes share: font loading,
text rendering, aspect-fit resizing, a progress bar, and a seamless marquee
window. All pure-Pillow, so they run and test anywhere (no hardware needed).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BLACK = (0, 0, 0)

# Font candidates: the Pi (DejaVu, installed by install.sh) first, then common
# macOS paths for off-Pi development.
_REGULAR_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
)
_BOLD_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
)


@lru_cache(maxsize=32)
def load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return a TTF font at ``size`` (cached), or Pillow's bitmap default if none found."""
    for path in _BOLD_FONTS if bold else _REGULAR_FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_size(text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    """Width and height of ``text`` in ``font`` (tight ink box)."""
    left, top, right, bottom = font.getbbox(text)
    return right - left, bottom - top


def render_text(
    text: str,
    font: ImageFont.ImageFont,
    color: tuple[int, int, int],
    *,
    bg: tuple[int, int, int] = BLACK,
) -> Image.Image:
    """Render ``text`` to a tight RGB image (ink-box sized)."""
    left, top, right, bottom = font.getbbox(text)
    img = Image.new("RGB", (max(1, right - left), max(1, bottom - top)), bg)
    ImageDraw.Draw(img).text((-left, -top), text, font=font, fill=color)
    return img


def fit(image: Image.Image, width: int, height: int) -> Image.Image:
    """Aspect-fit ``image`` within ``width``x``height`` (never upscales beyond it)."""
    out = image.copy()
    out.thumbnail((width, height), Image.LANCZOS)
    return out


def paste_center(canvas: Image.Image, image: Image.Image, *, use_alpha: bool = True) -> None:
    """Paste ``image`` centered on ``canvas`` (in place), using alpha as mask if present."""
    offset = ((canvas.width - image.width) // 2, (canvas.height - image.height) // 2)
    mask = image if (use_alpha and image.mode in ("RGBA", "LA")) else None
    canvas.paste(image, offset, mask)


def draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fraction: float,
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
    *,
    border: tuple[int, int, int] | None = None,
) -> None:
    """Draw a horizontal progress bar in ``box`` filled to ``fraction`` (0..1)."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=bg, outline=border)
    fraction = max(0.0, min(1.0, fraction))
    fill_w = round((x1 - x0) * fraction)
    if fill_w > 0:
        draw.rectangle((x0, y0, x0 + fill_w, y1), fill=fg)


def scroll_window(
    content: Image.Image,
    width: int,
    offset: int,
    *,
    gap: int = 8,
    bg: tuple[int, int, int] = BLACK,
) -> Image.Image:
    """A ``width``-wide window of ``content`` scrolled left by ``offset`` px.

    The content repeats with ``gap`` px between copies, so incrementing ``offset``
    each frame yields a seamless looping marquee. ``content.height`` is preserved.
    """
    period = content.width + gap
    start = -(offset % period)
    window = Image.new("RGB", (width, content.height), bg)
    x = start
    while x < width:
        window.paste(content, (x, 0))
        x += period
    return window


def needs_scroll(text: str, font: ImageFont.ImageFont, width: int) -> bool:
    """True if ``text`` is wider than ``width`` (i.e. it should be marquee'd)."""
    return text_size(text, font)[0] > width
