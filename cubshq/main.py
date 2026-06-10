"""Entry point: hosts the now-playing Flask ingest, runs the tick loop, and
dispatches to the active display mode.

Run as root on the Pi via the systemd service:  python -m cubshq.main

TODO: implement after state.py and display.py.
"""

from __future__ import annotations
