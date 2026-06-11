#!/usr/bin/env python3
"""Mac Mini companion — pushes Apple Music now-playing state to the cubs-hq Pi.

Launch manually on the Mac (not a service); stop with Ctrl-C:

    python3 companion/apple_music_sender.py

Every COMPANION_POLL_S seconds it reads the Music app via AppleScript and POSTs
{track, artist, album, art_b64, position, duration, state} to the Pi. Album art
is re-fetched only when the track changes. Stdlib only — no pip installs needed.
"""

from __future__ import annotations

import base64
import json
import subprocess
import time
import urllib.error
import urllib.request

PI_URL = "http://cubs-hq.local:5000/now-playing"
COMPANION_POLL_S = 2
_ART_TMP = "/tmp/cubshq_art.dat"

# Returns a tab-delimited line: "state[\ttrack\tartist\talbum\tposition\tduration]".
# Guards on the process existing so querying never launches Music.
_META_SCRIPT = r"""
tell application "System Events"
    if not (exists process "Music") then return "not_running"
end tell
tell application "Music"
    set s to (player state as string)
    if s is "playing" or s is "paused" then
        try
            return s & tab & (name of current track) & tab & (artist of current track) ¬
                & tab & (album of current track) & tab & ((player position) as string) ¬
                & tab & ((duration of current track) as string)
        on error
            return s
        end try
    end if
    return s
end tell
"""

# Writes the current track's artwork bytes to _ART_TMP; returns "ok" or "no".
_ART_SCRIPT = rf"""
tell application "System Events"
    if not (exists process "Music") then return "no"
end tell
tell application "Music"
    try
        if player state is stopped then return "no"
        set artData to raw data of artwork 1 of current track
        set fp to (open for access (POSIX file "{_ART_TMP}") with write permission)
        set eof fp to 0
        write artData to fp
        close access fp
        return "ok"
    on error
        try
            close access (POSIX file "{_ART_TMP}")
        end try
        return "no"
    end try
end tell
"""


def _osascript(script: str) -> str | None:
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=8, check=False
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def fetch_metadata() -> dict | None:
    """Current now-playing metadata, or None if Music isn't reachable."""
    raw = _osascript(_META_SCRIPT)
    if raw is None or raw == "not_running":
        return None
    parts = raw.split("\t")
    state = parts[0].strip().lower()
    if state in ("playing", "paused") and len(parts) >= 6:
        return {
            "state": state,
            "track": parts[1],
            "artist": parts[2],
            "album": parts[3],
            "position": _as_float(parts[4]),
            "duration": _as_float(parts[5]),
        }
    return {"state": state if state in ("playing", "paused") else "stopped"}


def fetch_art_b64() -> str:
    """Base64 of the current artwork (any image format), or '' if unavailable."""
    if _osascript(_ART_SCRIPT) != "ok":
        return ""
    try:
        with open(_ART_TMP, "rb") as handle:
            data = handle.read()
    except OSError:
        return ""
    return base64.b64encode(data).decode() if data else ""


def _as_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def post(payload: dict) -> bool:
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        PI_URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(request, timeout=5).read()  # noqa: S310 (trusted LAN URL)
    except (urllib.error.URLError, OSError):
        return False
    return True


def main() -> None:
    print(f"cubs-hq companion → {PI_URL}  (Ctrl-C to stop)")
    last_track: tuple[str, str] | None = None
    art_b64 = ""
    reachable = True
    while True:
        meta = fetch_metadata()
        if meta and meta.get("state") in ("playing", "paused"):
            track_key = (meta["track"], meta["artist"])
            if track_key != last_track:
                art_b64 = fetch_art_b64()
                last_track = track_key
            meta["art_b64"] = art_b64
            payload = meta
        else:
            last_track = None
            payload = {"state": "stopped"}

        ok = post(payload)
        if ok != reachable:  # log only on connectivity transitions
            print("Pi reachable" if ok else f"Pi unreachable at {PI_URL} — retrying…")
            reachable = ok
        time.sleep(COMPANION_POLL_S)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
