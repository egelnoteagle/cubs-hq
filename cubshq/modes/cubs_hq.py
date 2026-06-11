"""Mode 3 — Cubs HQ rotating idle display.

Cycles three screens on an IDLE_ROTATE_S (~10s) loop:
  A) the Cubs logo centered on black
  B) NL Central standings (abbrev, W-L, GB)
  C) the next Cubs game (date, CT time, opponent, probable pitchers)

A screen is rebuilt only when the rotation changes or the data is stale, so the
single-core Pi Zero W isn't re-rendering text every frame.
"""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image, ImageDraw

from cubshq import image_utils as iu
from cubshq import mlb
from cubshq.display import HEIGHT, WIDTH

IDLE_ROTATE_S = 10  # seconds per screen
_DATA_REFRESH_S = 60  # also rebuild the live screen at least this often

CUBS_BLUE = (14, 51, 134)
CUBS_RED = (204, 52, 51)
HILITE = (90, 150, 255)  # bright blue to mark the Cubs' own row
WHITE = (235, 235, 235)
GREY = (130, 130, 130)
BLACK = (0, 0, 0)


def _last_name(full: str | None) -> str:
    return full.split()[-1] if full else "TBD"


class CubsHQMode:
    """Rotates logo → standings → next game, rebuilding a screen only as needed."""

    def __init__(self, assets_dir: Path) -> None:
        self._logo = Image.open(assets_dir / "cubs_logo_64x64.png").convert("RGB")
        self._builders = (self._logo_screen, self._standings_screen, self._next_game_screen)
        self._index = -1
        self._built_at = 0.0
        self._frame = Image.new("RGB", (WIDTH, HEIGHT), BLACK)

    def render(self) -> Image.Image:
        now = time.monotonic()
        index = int(now // IDLE_ROTATE_S) % len(self._builders)
        if index != self._index or (now - self._built_at) > _DATA_REFRESH_S:
            self._frame = self._builders[index]()
            self._index = index
            self._built_at = now
        return self._frame

    @staticmethod
    def _blank() -> Image.Image:
        return Image.new("RGB", (WIDTH, HEIGHT), BLACK)

    def _logo_screen(self) -> Image.Image:
        canvas = self._blank()
        iu.paste_center(canvas, self._logo)
        return canvas

    def _standings_screen(self) -> Image.Image:
        canvas = self._blank()
        draw = ImageDraw.Draw(canvas)
        draw.text((2, 0), "NL CENTRAL", font=iu.load_font(7, bold=True), fill=CUBS_RED)
        row_font = iu.load_font(8)
        y = 11
        for team in mlb.nl_central_standings()[:5]:
            color = HILITE if team.abbrev == "CHC" else WHITE
            draw.text((2, y), team.abbrev, font=row_font, fill=color)
            draw.text((23, y), f"{team.wins:>2}-{team.losses:<2}", font=row_font, fill=color)
            draw.text((51, y), team.games_back, font=iu.load_font(7), fill=GREY)
            y += 10
        return canvas

    def _next_game_screen(self) -> Image.Image:
        canvas = self._blank()
        draw = ImageDraw.Draw(canvas)
        draw.text((2, 0), "NEXT GAME", font=iu.load_font(7, bold=True), fill=CUBS_RED)
        game = mlb.next_game()
        if game is None:
            body = iu.load_font(9)
            draw.text((2, 18), "No game", font=body, fill=WHITE)
            draw.text((2, 30), "scheduled", font=body, fill=WHITE)
            return canvas
        when = game.start_ct
        time_str = f"{when.strftime('%-I:%M%p').lower()} CT"
        matchup = f"{'vs' if game.cubs_home else '@'} {game.opponent_abbrev}"
        draw.text((2, 12), f"{when:%a %-m/%-d}", font=iu.load_font(8), fill=WHITE)
        draw.text((2, 22), time_str, font=iu.load_font(8), fill=WHITE)
        draw.text((2, 33), matchup, font=iu.load_font(10, bold=True), fill=HILITE)
        small = iu.load_font(7)
        draw.text((2, 47), f"CHC {_last_name(game.cubs_pitcher)}", font=small, fill=WHITE)
        opp = game.opponent_abbrev
        draw.text((2, 56), f"{opp} {_last_name(game.opponent_pitcher)}", font=small, fill=GREY)
        return canvas
