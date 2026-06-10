"""rpi-rgb-led-matrix wrapper.

Configures the matrix (adafruit-hat mapping, V-mapper, gpio_slowdown=2) and
exposes drawing helpers. Detects the absence of the ``rgbmatrix`` module and
falls back to log-only stubs so every other module is testable off-Pi.

TODO: implement (second module to be written).
"""

from __future__ import annotations
