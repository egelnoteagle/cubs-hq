"""Mode 2 — W Flag: the full-screen Cubs win flag.

Shown when Apple Music is idle, today's Cubs game is Final, and the Cubs won.
Just renders the pre-generated ``w_flag_64x64.png`` asset.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from cubshq.display import HEIGHT, WIDTH


class WFlagMode:
    """Renders the static W-flag asset full-screen."""

    def __init__(self, assets_dir: Path) -> None:
        frame = Image.open(assets_dir / "w_flag_64x64.png").convert("RGB")
        if frame.size != (WIDTH, HEIGHT):
            frame = frame.resize((WIDTH, HEIGHT))
        self._frame = frame

    def render(self) -> Image.Image:
        return self._frame
