"""Display-mode enum and transition logic.

`main.py` samples the current `Conditions` each tick and asks `StateMachine`
which mode should be on screen. Priority (first match wins):

    Apple Music  >  W Flag  >  Cubs HQ (idle)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Mode(Enum):
    """The three things the panel can show, highest priority first."""

    APPLE_MUSIC = "apple_music"
    W_FLAG = "w_flag"
    CUBS_HQ = "cubs_hq"


@dataclass(frozen=True)
class Conditions:
    """Inputs that decide the active mode, sampled by `main.py` each tick.

    Keeping mode selection a pure function of these flags makes it trivial to
    unit-test off-Pi without the matrix, the MLB API, or the music feed.
    """

    music_active: bool
    """A fresh `playing` now-playing payload arrived within the timeout."""

    cubs_won_today: bool
    """Today's Cubs game is Final and the Cubs won (resets at local midnight)."""


def resolve_mode(conditions: Conditions) -> Mode:
    """Return the active mode for the given conditions, by priority."""
    if conditions.music_active:
        return Mode.APPLE_MUSIC
    if conditions.cubs_won_today:
        return Mode.W_FLAG
    return Mode.CUBS_HQ


class StateMachine:
    """Tracks the active mode across ticks and flags transitions.

    A transition is the cue for `main.py` to clear the panel / reset any
    per-mode animation state before handing off to the new mode.
    """

    def __init__(self) -> None:
        self._mode: Mode | None = None

    @property
    def mode(self) -> Mode | None:
        """The mode chosen on the last `update`, or None before the first."""
        return self._mode

    def update(self, conditions: Conditions) -> tuple[Mode, bool]:
        """Resolve the mode for `conditions`.

        Returns `(mode, changed)` where `changed` is True iff the mode differs
        from the previous tick (also True on the very first update).
        """
        new_mode = resolve_mode(conditions)
        changed = new_mode is not self._mode
        self._mode = new_mode
        return new_mode, changed
