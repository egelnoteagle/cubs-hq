# cubs-hq

A Raspberry Pi Zero W daemon that drives a **64×64 RGB LED matrix** as a Chicago Cubs status display.

It runs a small state machine that shows one of three screens by priority:

1. **Apple Music** — live now-playing, mirrored from a Mac Mini on the LAN (album art, scrolling track/artist, progress bar).
2. **W Flag** — full-screen "W" when the Cubs win today's game.
3. **Cubs HQ** — rotating idle display: logo → NL Central standings → next game with probable pitchers.

## Hardware

- Raspberry Pi Zero W V1.1 (ARMv6, 512 MB)
- Adafruit RGB Matrix Bonnet (Zero form factor)
- 2× Waveshare P2.5 64×32 HUB75 panels, stacked vertically → 64×64
- Panels powered by their shared 5 V Y-cable; data daisy-chained Bonnet → panel 1 → panel 2

Matrix config: `--led-rows=32 --led-cols=64 --led-chain=2 --led-pixel-mapper=V-mapper`, `hardware_mapping=adafruit-hat`, `gpio_slowdown=2`.

## Install (on the Pi)

```bash
git clone https://github.com/egelnoteagle/cubs-hq.git
cd cubs-hq
# drop your high-res logo in: assets/cubs_logo_source.png
sudo bash install.sh
```

This builds `rpi-rgb-led-matrix` from source, creates a venv, generates the display assets, and installs the `cubs-hq` systemd service.

## Apple Music companion (on the Mac Mini)

```bash
python3 companion/apple_music_sender.py
```

Polls Apple Music every 2 s and POSTs now-playing metadata to `http://cubs-hq.local:5000/now-playing`. Leave it running to use Mode 1.

## Service management

```bash
sudo systemctl status cubs-hq
sudo journalctl -u cubs-hq -f
```

## Development

- Python 3.11+, type hints, linted with `ruff` (`ruff check .`).
- `cubshq/display.py` stubs out when `rgbmatrix` is unavailable, so everything except the display layer can be run and tested off-Pi.

See [CLAUDE.md](CLAUDE.md) for full architecture, mode logic, API details, and constraints.
