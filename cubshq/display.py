"""rpi-rgb-led-matrix wrapper for the 64x64 panel.

Configures the matrix for the cubs-hq hardware (Adafruit Bonnet → two stacked
64x32 P2.5 panels reshaped to 64x64 by the V-mapper) and exposes a tiny
``Display`` API: ``show(image)`` and ``clear()``.

If the ``rgbmatrix`` bindings are not importable (i.e. anywhere that isn't the
Pi), ``Display`` degrades to log-only no-ops so every other module — modes,
mlb, image_utils, the state machine — can be developed and tested off-Pi.
"""

from __future__ import annotations

import logging

from PIL import Image

logger = logging.getLogger(__name__)

# Logical panel geometry (after the V-mapper stacks the two 64x32 panels).
WIDTH = 64
HEIGHT = 64

# Matrix tuning — see the "Hardware" section of CLAUDE.md.
HARDWARE_MAPPING = "adafruit-hat"  # the Bonnet uses the HAT's GPIO mapping
LED_ROWS = 32
LED_COLS = 64
LED_CHAIN = 2
PIXEL_MAPPER = "V-mapper"  # stack the 2-long chain into a 64x64 square
GPIO_SLOWDOWN = 2  # Zero 2 W starting value; raise to 3 if flicker/ghosting
DEFAULT_BRIGHTNESS = 80  # 0–100
LED_RGB_SEQUENCE = "RBG"  # these Waveshare panels wire green/blue swapped vs the RGB default

BLACK = (0, 0, 0)

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions

    _MATRIX_AVAILABLE = True
except ImportError:  # not on a Pi / bindings not built
    RGBMatrix = None  # type: ignore[assignment,misc]
    RGBMatrixOptions = None  # type: ignore[assignment,misc]
    _MATRIX_AVAILABLE = False


def matrix_available() -> bool:
    """True when the rgbmatrix bindings are present (i.e. running on the Pi)."""
    return _MATRIX_AVAILABLE


def _build_options(brightness: int) -> RGBMatrixOptions:
    options = RGBMatrixOptions()
    options.hardware_mapping = HARDWARE_MAPPING
    options.rows = LED_ROWS
    options.cols = LED_COLS
    options.chain_length = LED_CHAIN
    options.parallel = 1
    options.pixel_mapper_config = PIXEL_MAPPER
    options.gpio_slowdown = GPIO_SLOWDOWN
    options.brightness = brightness
    options.led_rgb_sequence = LED_RGB_SEQUENCE
    # The daemon runs as root for GPIO/DMA; don't let the library drop to
    # 'daemon' after init (it can break file/network access the daemon needs).
    options.drop_privileges = False
    return options


class Display:
    """A 64x64 frame sink: render a PIL image or clear the panel.

    Double-buffered via a frame canvas + ``SwapOnVSync`` so per-frame updates
    (marquee scroll, progress bar) are tear-free.
    """

    def __init__(self, brightness: int = DEFAULT_BRIGHTNESS) -> None:
        self.brightness = brightness
        self._matrix: RGBMatrix | None = None
        self._canvas = None
        if _MATRIX_AVAILABLE:
            self._matrix = RGBMatrix(options=_build_options(brightness))
            self._canvas = self._matrix.CreateFrameCanvas()
            logger.info(
                "Matrix initialised: %dx%d, mapping=%s, slowdown=%d, brightness=%d",
                WIDTH,
                HEIGHT,
                HARDWARE_MAPPING,
                GPIO_SLOWDOWN,
                brightness,
            )
        else:
            logger.warning("rgbmatrix unavailable — Display in stub mode (no hardware output)")

    @property
    def size(self) -> tuple[int, int]:
        """Panel size as ``(width, height)``."""
        return (WIDTH, HEIGHT)

    def show(self, image: Image.Image) -> None:
        """Render ``image`` as the next frame.

        The image is converted to RGB and, if it isn't already 64x64, centered
        on a black frame (smaller) or cropped (larger).
        """
        frame = self._normalise(image)
        if self._matrix is None or self._canvas is None:
            logger.debug("stub show(): would render a %dx%d frame", *frame.size)
            return
        self._canvas.SetImage(frame)
        self._canvas = self._matrix.SwapOnVSync(self._canvas)

    def clear(self) -> None:
        """Blank the panel."""
        if self._matrix is None:
            logger.debug("stub clear()")
            return
        self._matrix.Clear()
        if self._canvas is not None:
            self._canvas.Clear()

    @staticmethod
    def _normalise(image: Image.Image) -> Image.Image:
        """Return ``image`` as a 64x64 RGB frame (convert + center/crop)."""
        if image.mode != "RGB":
            image = image.convert("RGB")
        if image.size == (WIDTH, HEIGHT):
            return image
        frame = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        offset = ((WIDTH - image.width) // 2, (HEIGHT - image.height) // 2)
        frame.paste(image, offset)
        return frame
