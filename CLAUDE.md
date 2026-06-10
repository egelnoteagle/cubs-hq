# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

`cubs-hq` is a Raspberry Pi Zero W daemon that drives a **64×64 RGB LED matrix** as a Chicago Cubs status display. It runs a small state machine that picks one of three display modes by priority:

1. **Apple Music** — now-playing screen, mirrored live from a Mac Mini on the LAN (highest priority).
2. **W Flag** — full-screen "W" flag when the Cubs have won today's game.
3. **Cubs HQ** — a rotating idle display (logo, NL Central standings, next game) when nothing else applies.

A single systemd service (`cubs-hq.service`) runs the daemon as root. A standalone companion script runs on the Mac Mini to push Apple Music metadata to the Pi.

> Status: scaffolding only. Application modules under `cubshq/` are intentionally stubs — implementation begins with `state.py` and `display.py`. `prepare_assets.py` is implemented.

## Hardware

| Component | Detail |
|---|---|
| SBC | Raspberry Pi Zero W **V1.1** — BCM2835, **ARMv6**, single-core 1 GHz, **512 MB RAM** |
| HAT | **Adafruit RGB Matrix Bonnet** (Zero form factor, *not* the HAT) |
| Panels | 2× **Waveshare P2.5 64×32 HUB75**, stacked **vertically** → 64×64 logical |
| Data wiring | Bonnet output → **panel 1 IN**; **panel 1 OUT → panel 2 IN** (daisy-chained) |
| Power | Shared 5 V via the Y-cable included with the panels (do **not** power panels from the Pi) |

### Critical matrix configuration

The two 64×32 panels are one chain of length 2, reshaped into a 64×64 square by the **V-mapper** (vertical mapper):

```
--led-rows=32 --led-cols=64 --led-chain=2 --led-pixel-mapper=V-mapper
```

- **Hardware mapping:** `adafruit-hat` (the Bonnet uses the same GPIO mapping as the Adafruit HAT). Set `options.hardware_mapping = "adafruit-hat"` in `display.py`.
- **`gpio_slowdown = 2`** is required for Pi Zero W stability (the single 1 GHz core outruns the panels at slowdown 1 and flickers). Raise to 3 only if flicker persists.
- Logical coordinate space after mapping: `(0,0)` top-left → `(63,63)` bottom-right. Panel 1 is the top half (rows 0–31), panel 2 the bottom half (rows 32–63).
- The Bonnet does **not** have the HAT's PWM-quality solder jumper. If you see image ghosting, that's expected to be tuned via `pwm_bits` / `pwm_lsb_nanoseconds`, not a jumper.

## Display mode logic (state machine)

Priority order (first match wins), re-evaluated every tick:

```
Apple Music  >  W Flag  >  Cubs HQ (idle)
```

### Mode 1 — Apple Music  (`cubshq/modes/apple_music.py`)
- **Trigger:** the Pi's Flask endpoint has received a now-playing POST within the last **10 s** *and* the reported playback `state` is `playing`.
- **Fallback:** when music stops, pauses, or metadata stops arriving (10 s timeout), drop to Mode 2 or 3.
- **Layout (64×64):**
  - Album art scaled to the upper portion.
  - Track name — scrolling marquee if it overflows the width.
  - Artist name.
  - Playback progress bar along the bottom edge.

### Mode 2 — W Flag  (`cubshq/modes/w_flag.py`)
- **Trigger:** Apple Music inactive **AND** today's Cubs game `abstractGameState == "Final"` **AND** the Cubs won.
- **Display:** `assets/w_flag_64x64.png` full screen.
- **Reset:** clears at local midnight (new day → no longer "today's win").

### Mode 3 — Cubs HQ idle  (`cubshq/modes/cubs_hq.py`)
- **Trigger:** Apple Music inactive **AND** no Cubs game has started or completed today (pre-game, or no game scheduled).
- **Display:** rotates three screens on a ~**10 s** cycle:
  - **A** — `assets/cubs_logo_64x64.png` centered on black.
  - **B** — NL Central standings: rank, team abbreviation, W, L, GB for all 5 teams.
  - **C** — Next Cubs game: date, time (CT), opponent abbreviation, probable starting pitchers for both teams (last name only if space is tight).

## Data sources

### MLB Stats API — `statsapi.mlb.com` (free, unauthenticated)
- Cubs **teamId = 112**
- NL Central **divisionId = 205**
- National League **leagueId = 104**
- `abstractGameState` cycles `Preview → Live → Final`; only `Final` drives Mode 2.

Endpoints used:

```
# NL Central standings
https://statsapi.mlb.com/api/v1/standings?leagueId=104&season=2026&standingsTypes=regularSeason

# Cubs schedule + probable pitchers (today through 30 days out)
https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=112&startDate=TODAY&endDate=30_DAYS_OUT&hydrate=probablePitcher
```

All MLB access lives in `cubshq/mlb.py`. Keep requests lean and cache responses in memory between ticks — the Pi Zero W is bandwidth- and CPU-constrained, and these endpoints rarely change within a polling interval.

### Apple Music — companion script protocol
- `companion/apple_music_sender.py` runs on the **Mac Mini** (a script the user launches manually, *not* a service).
- Every **2 s** it reads Apple Music now-playing state via AppleScript and POSTs JSON to:

```
POST http://cubs-hq.local:5000/now-playing
```

- **Payload fields:** `track` (name), `artist`, `album`, `art_b64` (base64 album art), `position` (seconds), `duration` (seconds), `state` (`playing` | `paused` | `stopped`).
- The Pi runs a lightweight Flask server (started by the daemon) that stores the latest payload plus a receipt timestamp. Mode 1 is active only while a `playing` payload is fresher than the 10 s timeout.

## Constraints

- **Python 3.11+**, type hints throughout, clean modern style.
- **Minimal memory/CPU** — Pi Zero W is single-core, 512 MB. Avoid per-tick allocations of large images; pre-render and cache.
- **`ruff`** for linting (config in `ruff.toml`).
- All LED matrix operations go through the **`hzeller/rpi-rgb-led-matrix`** Python bindings, **built from source** by `install.sh` (there is no pip package).
- The daemon runs as a **single systemd service** managing all modes.
- **Dependencies:** `requests`, `Pillow`, `schedule`, `flask` only — no heavy frameworks.
- `display.py` must **stub gracefully off-Pi**: detect the absence of `rgbmatrix` and fall back to log-only no-ops, so every module except `display.py` can be developed/tested on a non-Pi machine.

## Repository layout

```
cubs-hq/
  assets/
    cubs_logo_source.png    # provided by the user — high-res Cubs logo (input)
    w_flag_64x64.png        # generated by prepare_assets.py (gitignored)
    cubs_logo_64x64.png     # generated by prepare_assets.py (gitignored)
  cubshq/
    __init__.py
    main.py                 # entry point: Flask server + tick loop + mode dispatch
    state.py                # Mode enum + transition logic
    display.py              # rpi-rgb-led-matrix wrapper (stubs off-Pi)
    modes/
      __init__.py
      apple_music.py        # Mode 1
      w_flag.py             # Mode 2
      cubs_hq.py            # Mode 3 (rotating idle)
    mlb.py                  # MLB Stats API client
    image_utils.py          # Pillow helpers (resize, text rendering, marquee)
  companion/
    apple_music_sender.py   # runs on the Mac Mini, posts now-playing to the Pi
  prepare_assets.py         # one-shot: build the two 64×64 display assets
  install.sh                # builds matrix lib, venv, assets, systemd service
  cubs-hq.service.template   # systemd unit template
  requirements.txt
  ruff.toml
  README.md
  CLAUDE.md
```

## Setup (on the Pi)

```bash
sudo bash install.sh        # builds rpi-rgb-led-matrix, creates venv, generates assets, installs the service
```

`install.sh` is idempotent. It installs system deps (incl. `fonts-dejavu-core` for the W glyph), clones/builds `rpi-rgb-led-matrix` into `/opt/rpi-rgb-led-matrix`, creates a venv, installs `requirements.txt`, runs `prepare_assets.py`, and installs + enables `cubs-hq.service`.

### Assets

```bash
python3 prepare_assets.py   # regenerate w_flag_64x64.png and cubs_logo_64x64.png
```

- `w_flag_64x64.png` is generated **programmatically** — Cubs blue (`#0E3386`) background, bold white "W" sized to fill the panel. No source image needed.
- `cubs_logo_64x64.png` is resized from `assets/cubs_logo_source.png` (preserve transparency, composite onto black for LED rendering). Drop the source PNG in before running.

## Service management

```bash
sudo systemctl status cubs-hq
sudo journalctl -u cubs-hq -f
```

## Key constants (in their respective files)

| Constant | File | Default | Meaning |
|---|---|---|---|
| `NOW_PLAYING_TIMEOUT_S` | `main.py` | `10` | Drop Mode 1 if no fresh `playing` payload within this window |
| `IDLE_ROTATE_S` | `modes/cubs_hq.py` | `10` | Seconds per idle screen (A/B/C) |
| `COMPANION_POLL_S` | `companion/apple_music_sender.py` | `2` | AppleScript now-playing poll interval |
| `FLASK_PORT` | `main.py` | `5000` | Now-playing ingest port |
| `options.hardware_mapping` | `display.py` | `"adafruit-hat"` | Bonnet uses the HAT mapping |
| `options.gpio_slowdown` | `display.py` | `2` | Pi Zero W stability |
| `options.brightness` | `display.py` | `80` | 0–100 |

## Development notes

- `display.py` detects the absence of `rgbmatrix` and falls back to log-only stubs, so all code except `display.py` can be tested on a non-Pi machine (e.g. the Mac Mini).
- The MLB season for endpoints is **2026**.
- Keep generated assets out of git (see `.gitignore`); only `cubs_logo_source.png` is committed.
