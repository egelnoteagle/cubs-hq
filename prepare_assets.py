#!/usr/bin/env python3
"""Generate the two 64x64 display assets for cubs-hq.

Outputs (written to ``assets/``):

* ``w_flag_64x64.png``  — built programmatically: white background with a bold
  Cubs-blue "W" sized to fill the panel (the Wrigley Field win flag). No source image
  required.
* ``cubs_logo_64x64.png`` — resized from ``assets/cubs_logo_source.png``,
  transparency preserved and composited onto black for clean LED rendering.

Run directly (``python3 prepare_assets.py``) or via ``install.sh`` on the Pi.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 64
CUBS_BLUE = (14, 51, 134)  # #0E3386
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

ASSETS = Path(__file__).resolve().parent / "assets"
W_FLAG_OUT = ASSETS / "w_flag_64x64.png"
LOGO_SOURCE = ASSETS / "cubs_logo_source.png"
LOGO_OUT = ASSETS / "cubs_logo_64x64.png"

# Bold TTF candidates, in priority order: the Pi (DejaVu, installed by install.sh)
# first, then common macOS paths for off-Pi testing.
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


def _find_bold_font() -> str | None:
    """Return the first available bold TTF path, or None to fall back to a bitmap font."""
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def _largest_fitting_font(
    text: str, target_px: int, font_path: str
) -> tuple[ImageFont.FreeTypeFont, tuple[int, int, int, int]]:
    """Find the largest font size whose rendered ``text`` ink fits within ``target_px``.

    Returns the chosen font and the glyph ink bbox ``(left, top, right, bottom)``.
    """
    chosen = ImageFont.truetype(font_path, 8)
    chosen_bbox = chosen.getbbox(text)
    for size in range(9, 200):
        font = ImageFont.truetype(font_path, size)
        left, top, right, bottom = font.getbbox(text)
        if (right - left) > target_px or (bottom - top) > target_px:
            break
        chosen, chosen_bbox = font, (left, top, right, bottom)
    return chosen, chosen_bbox


def build_w_flag() -> None:
    """Render the Cubs win flag (white field, blue "W") and write ``w_flag_64x64.png``."""
    img = Image.new("RGB", (SIZE, SIZE), WHITE)
    draw = ImageDraw.Draw(img)

    font_path = _find_bold_font()
    if font_path is None:
        # Last resort: Pillow's built-in bitmap font (small, but never crashes).
        font = ImageFont.load_default()
        draw.text((SIZE // 2, SIZE // 2), "W", font=font, fill=CUBS_BLUE, anchor="mm")
        print("  WARNING: no bold TTF found; used Pillow's default bitmap font for the W.")
    else:
        # Leave a 2px breathing margin on every side.
        font, (left, top, right, bottom) = _largest_fitting_font("W", SIZE - 4, font_path)
        ink_w, ink_h = right - left, bottom - top
        x = (SIZE - ink_w) // 2 - left
        y = (SIZE - ink_h) // 2 - top
        draw.text((x, y), "W", font=font, fill=CUBS_BLUE)

    img.save(W_FLAG_OUT)
    print(f"  wrote {W_FLAG_OUT.relative_to(ASSETS.parent)}")


def build_logo() -> None:
    """Resize the source Cubs logo to 64x64 on black and write ``cubs_logo_64x64.png``."""
    if not LOGO_SOURCE.exists():
        print(
            f"  SKIP: {LOGO_SOURCE.relative_to(ASSETS.parent)} not found — "
            "drop your high-res logo there and re-run."
        )
        return

    logo = Image.open(LOGO_SOURCE).convert("RGBA")
    logo.thumbnail((SIZE, SIZE), Image.LANCZOS)  # preserve aspect ratio, fit within 64x64

    canvas = Image.new("RGB", (SIZE, SIZE), BLACK)
    offset = ((SIZE - logo.width) // 2, (SIZE - logo.height) // 2)
    canvas.paste(logo, offset, logo)  # use the alpha channel as the paste mask
    canvas.save(LOGO_OUT)
    print(f"  wrote {LOGO_OUT.relative_to(ASSETS.parent)}")


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    print("Generating cubs-hq display assets:")
    build_w_flag()
    build_logo()


if __name__ == "__main__":
    main()
