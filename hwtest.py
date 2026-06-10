#!/usr/bin/env python3
"""Hardware bring-up test for the cubs-hq 64x64 panel.

Run on the Pi as root (GPIO/DMA need it):

    cd ~/cubs-hq && sudo .venv/bin/python hwtest.py

It cycles through solid colors, an orientation frame, and the real assets so you
can confirm — before any daemon exists — that:

* the panel lights up at all (wiring + power + GPIO),
* the V-mapper stitches the two 64x32 panels into one upright 64x64 image
  (orientation frame: white square top-left, red square bottom-right),
* color order is correct (the RED/GREEN/BLUE screens match their labels),
* there's no objectionable flicker (if there is, bump gpio_slowdown in display.py).

Ctrl-C to stop early; the panel is cleared on exit.
"""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image, ImageDraw

from cubshq.display import HEIGHT, WIDTH, Display, matrix_available

ASSETS = Path(__file__).resolve().parent / "assets"


def _hold(display: Display, image: Image.Image, label: str, seconds: float) -> None:
    print(f"  {label}  ({seconds:.0f}s)")
    display.show(image)
    time.sleep(seconds)


def _solid(color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", (WIDTH, HEIGHT), color)


def _orientation_frame() -> Image.Image:
    """A frame that makes geometry/orientation obvious at a glance."""
    img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), outline=(0, 255, 0))  # green border
    draw.line((0, 0, WIDTH - 1, HEIGHT - 1), fill=(0, 128, 255))  # TL->BR diagonal
    draw.rectangle((0, 0, 7, 7), fill=(255, 255, 255))  # white square top-left
    draw.rectangle((WIDTH - 8, HEIGHT - 8, WIDTH - 1, HEIGHT - 1), fill=(255, 0, 0))  # red BR
    return img


def main() -> None:
    print(f"matrix_available: {matrix_available()}  (False means no hardware — stub mode)")
    display = Display()
    try:
        _hold(display, _solid((255, 0, 0)), "RED screen", 2)
        _hold(display, _solid((0, 255, 0)), "GREEN screen", 2)
        _hold(display, _solid((0, 0, 255)), "BLUE screen", 2)
        _hold(display, _orientation_frame(), "ORIENTATION: white@top-left, red@bottom-right", 6)
        _hold(display, Image.open(ASSETS / "w_flag_64x64.png"), "W FLAG (blue W on white)", 6)
        _hold(display, Image.open(ASSETS / "cubs_logo_64x64.png"), "CUBS LOGO", 6)
        print("All frames shown.")
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        display.clear()
        print("panel cleared.")


if __name__ == "__main__":
    main()
