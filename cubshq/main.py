"""Entry point: now-playing Flask ingest + tick loop + mode dispatch.

Runs as root on the Pi via the systemd service: ``python -m cubshq.main``.
A background Flask thread receives now-playing POSTs from the Mac companion;
the main loop samples conditions each tick, asks the StateMachine which mode is
active, renders that mode's frame, and pushes it to the panel.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from flask import Flask, request

from cubshq import mlb
from cubshq.display import Display
from cubshq.modes.apple_music import AppleMusicMode, NowPlaying
from cubshq.modes.cubs_hq import CubsHQMode
from cubshq.modes.w_flag import WFlagMode
from cubshq.state import Conditions, Mode, StateMachine

logger = logging.getLogger(__name__)

NOW_PLAYING_TIMEOUT_S = 10  # drop Mode 1 if no fresh "playing" payload within this
FLASK_PORT = 5000
TICK_HZ = 20  # frame rate of the loop (smooth marquee without thrashing the CPU)
GAME_POLL_S = 120  # how often to re-check today's Cubs result
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


class NowPlayingStore:
    """Thread-safe holder for the latest now-playing snapshot."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: NowPlaying | None = None

    def update(self, now: NowPlaying) -> None:
        with self._lock:
            self._current = now

    def current(self) -> NowPlaying | None:
        with self._lock:
            return self._current

    def is_active(self) -> bool:
        """True while a fresh ``playing`` payload is within the timeout window."""
        now = self.current()
        return bool(
            now
            and now.state == "playing"
            and (time.monotonic() - now.received_at) < NOW_PLAYING_TIMEOUT_S
        )


def create_app(store: NowPlayingStore) -> Flask:
    app = Flask(__name__)

    @app.post("/now-playing")
    def now_playing() -> tuple[str, int]:
        store.update(NowPlaying.from_payload(request.get_json(force=True, silent=True) or {}))
        return ("", 204)

    @app.get("/healthz")
    def healthz() -> tuple[str, int]:
        return ("ok", 200)

    return app


def _serve(app: Flask) -> None:
    app.run(host="0.0.0.0", port=FLASK_PORT, threaded=True)


def run() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # quiet per-request logs

    display = Display()
    store = NowPlayingStore()
    threading.Thread(target=_serve, args=(create_app(store),), daemon=True).start()
    logger.info("now-playing ingest listening on :%d", FLASK_PORT)

    apple = AppleMusicMode()
    wflag = WFlagMode(ASSETS_DIR)
    cubshq = CubsHQMode(ASSETS_DIR)
    machine = StateMachine()

    cubs_won = False
    last_game_poll = 0.0
    period = 1.0 / TICK_HZ

    while True:
        tick_start = time.monotonic()

        if last_game_poll == 0.0 or (tick_start - last_game_poll) > GAME_POLL_S:
            cubs_won = mlb.did_cubs_win_today()
            last_game_poll = tick_start

        conditions = Conditions(music_active=store.is_active(), cubs_won_today=cubs_won)
        mode, changed = machine.update(conditions)
        if changed:
            logger.info("mode -> %s", mode.value)

        now = store.current()
        if mode is Mode.APPLE_MUSIC and now is not None:
            frame = apple.render(now)
        elif mode is Mode.W_FLAG:
            frame = wflag.render()
        else:
            frame = cubshq.render()
        display.show(frame)

        time.sleep(max(0.0, period - (time.monotonic() - tick_start)))


def main() -> None:
    try:
        run()
    except KeyboardInterrupt:
        logger.info("shutting down")


if __name__ == "__main__":
    main()
