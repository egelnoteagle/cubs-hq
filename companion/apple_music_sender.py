"""Mac Mini companion — pushes Apple Music now-playing state to the Pi.

Runs on the Mac Mini (launched manually, not a service). Every COMPANION_POLL_S
seconds it reads Apple Music now-playing via AppleScript and POSTs JSON
{track, artist, album, art_b64, position, duration, state} to
http://cubs-hq.local:5000/now-playing.

TODO: implement.
"""

from __future__ import annotations
