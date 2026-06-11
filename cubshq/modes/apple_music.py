"""Mode 1 — Apple Music now-playing.

Renders the latest now-playing payload (posted by the Mac Mini companion):
album art on top, a scrolling track marquee, the artist, and a bottom progress
bar. The ``NowPlaying`` dataclass is the wire format shared with ``main.py``.
"""

from __future__ import annotations

import base64
import binascii
import time
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageDraw

from cubshq import image_utils as iu
from cubshq.display import HEIGHT, WIDTH

WHITE = (235, 235, 235)
GREY = (150, 150, 150)
BLACK = (0, 0, 0)
BAR_BG = (45, 45, 45)
BAR_FG = (90, 150, 255)

_ART_H = 38  # album-art band height
_SCROLL_PX_PER_FRAME = 1


@dataclass
class NowPlaying:
    """A now-playing snapshot from the companion script."""

    track: str
    artist: str
    album: str
    position: float  # seconds elapsed
    duration: float  # seconds total
    state: str  # playing | paused | stopped
    received_at: float  # time.monotonic() when stored
    art: Image.Image | None = None

    @classmethod
    def from_payload(cls, data: dict) -> NowPlaying:
        """Build from the posted JSON, decoding base64 album art if present."""
        art = None
        encoded = data.get("art_b64")
        if encoded:
            try:
                art = Image.open(BytesIO(base64.b64decode(encoded))).convert("RGB")
            except (binascii.Error, ValueError, OSError):
                art = None
        return cls(
            track=str(data.get("track", "")),
            artist=str(data.get("artist", "")),
            album=str(data.get("album", "")),
            position=float(data.get("position", 0) or 0),
            duration=float(data.get("duration", 0) or 0),
            state=str(data.get("state", "stopped")),
            received_at=time.monotonic(),
            art=art,
        )


class AppleMusicMode:
    """Renders a now-playing frame, scrolling the track title when it overflows."""

    def __init__(self) -> None:
        self._scroll = 0
        self._last_track: str | None = None

    def render(self, now: NowPlaying) -> Image.Image:
        canvas = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(canvas)

        # Album art (or a placeholder block) centered in the top band.
        if now.art is not None:
            art = iu.fit(now.art, WIDTH, _ART_H)
            canvas.paste(art, ((WIDTH - art.width) // 2, (_ART_H - art.height) // 2))
        else:
            draw.rectangle((WIDTH // 2 - 16, 3, WIDTH // 2 + 16, _ART_H - 3), outline=GREY)
            draw.text((WIDTH // 2 - 4, _ART_H // 2 - 5), "♪", font=iu.load_font(11), fill=GREY)

        # Track title — marquee if it doesn't fit.
        track_font = iu.load_font(9, bold=True)
        if now.track != self._last_track:
            self._scroll = 0
            self._last_track = now.track
        strip = iu.render_text(now.track or "—", track_font, WHITE)
        if strip.width > WIDTH:
            canvas.paste(iu.scroll_window(strip, WIDTH, self._scroll), (0, _ART_H + 2))
            self._scroll += _SCROLL_PX_PER_FRAME
        else:
            canvas.paste(strip, ((WIDTH - strip.width) // 2, _ART_H + 2))

        # Artist (left-aligned; overflow clips at the panel edge).
        canvas.paste(iu.render_text(now.artist or "", iu.load_font(8), GREY), (2, _ART_H + 13))

        # Progress bar along the bottom.
        fraction = now.position / now.duration if now.duration > 0 else 0.0
        iu.draw_progress_bar(draw, (2, HEIGHT - 4, WIDTH - 3, HEIGHT - 2), fraction, BAR_FG, BAR_BG)
        return canvas
