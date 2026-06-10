#!/usr/bin/env bash
#
# cubs-hq installer — run on the Raspberry Pi:   sudo bash install.sh
#
# Idempotent. Installs system deps, builds rpi-rgb-led-matrix from source,
# creates a venv, generates display assets, and installs the systemd service.
#
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${APP_DIR}/.venv"
MATRIX_DIR="/opt/rpi-rgb-led-matrix"
SERVICE_NAME="cubs-hq.service"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

if [[ "${EUID}" -ne 0 ]]; then
    echo "Please run as root:  sudo bash install.sh" >&2
    exit 1
fi

# --- 1. System dependencies -------------------------------------------------
log "Installing system packages"
apt-get update
apt-get install -y \
    git build-essential cmake ninja-build \
    python3 python3-dev python3-venv python3-pip \
    libgraphicsmagick++-dev libwebp-dev \
    fonts-dejavu-core          # provides DejaVuSans-Bold.ttf for the W glyph
    # cmake + ninja: the rgbmatrix bindings build with scikit-build-core (CMake),
    # and there are no reliable armv6 wheels for them, so install from apt.

# --- 2. Build rpi-rgb-led-matrix (no pip package exists) ---------------------
if [[ ! -d "${MATRIX_DIR}/.git" ]]; then
    log "Cloning rpi-rgb-led-matrix into ${MATRIX_DIR}"
    git clone --depth=1 https://github.com/hzeller/rpi-rgb-led-matrix.git "${MATRIX_DIR}"
else
    log "Updating rpi-rgb-led-matrix"
    git -C "${MATRIX_DIR}" pull --ff-only || true
fi

log "Building the matrix core library"
make -C "${MATRIX_DIR}/lib"

# --- 3. Python venv + dependencies ------------------------------------------
if [[ ! -d "${VENV}" ]]; then
    log "Creating venv at ${VENV}"
    python3 -m venv "${VENV}"
fi
log "Installing Python dependencies"
"${VENV}/bin/pip" install --upgrade pip
"${VENV}/bin/pip" install -r "${APP_DIR}/requirements.txt"

log "Building + installing the rgbmatrix Python bindings into the venv"
# The bindings include a pillow.c shim that needs Pillow's internal C headers
# (Imaging.h), which are NOT shipped in binary wheels. Clone the matching Pillow
# source and feed its libImaging dir to the compiler via CPATH.
PILLOW_VERSION="$("${VENV}/bin/python" -c 'import PIL; print(PIL.__version__)')"
PILLOW_SRC="/tmp/pillow-src"
if [[ ! -d "${PILLOW_SRC}/src/libImaging" ]]; then
    log "Cloning Pillow ${PILLOW_VERSION} source for internal C headers (Imaging.h)"
    rm -rf "${PILLOW_SRC}"
    git clone --depth 1 --branch "${PILLOW_VERSION}" \
        https://github.com/python-pillow/Pillow.git "${PILLOW_SRC}"
fi
# Current rpi-rgb-led-matrix builds with scikit-build-core (CMake) via 'pip
# install .'; build isolation pulls scikit-build-core + cython, cmake/ninja come
# from apt above, and CPATH supplies Imaging.h to the pillow.c shim compile.
CPATH="${PILLOW_SRC}/src/libImaging${CPATH:+:${CPATH}}" \
    "${VENV}/bin/pip" install "${MATRIX_DIR}"

# --- 4. Generate display assets ---------------------------------------------
log "Generating display assets"
if [[ ! -f "${APP_DIR}/assets/cubs_logo_source.png" ]]; then
    echo "  WARNING: assets/cubs_logo_source.png not found — the W flag will still"
    echo "           be generated, but the logo screen will be missing. Add the"
    echo "           source PNG and re-run:  ${VENV}/bin/python prepare_assets.py"
fi
"${VENV}/bin/python" "${APP_DIR}/prepare_assets.py"

# --- 4b. Disable onboard audio ----------------------------------------------
# The hzeller library times the display with the hardware PWM peripheral, which
# the onboard sound module (snd_bcm2835) also claims. With audio enabled the
# matrix initialises but stays dark, so disable it (blacklist + device tree).
log "Disabling onboard audio (frees the PWM peripheral for the matrix)"
echo "blacklist snd_bcm2835" > /etc/modprobe.d/cubshq-no-audio.conf
for cfg in /boot/firmware/config.txt /boot/config.txt; do
    [ -f "$cfg" ] && sed -i 's/^dtparam=audio=on/dtparam=audio=off/' "$cfg"
done

# --- 5. systemd service -----------------------------------------------------
log "Installing ${SERVICE_NAME}"
RENDERED="${APP_DIR}/${SERVICE_NAME}"
sed -e "s|__APP_DIR__|${APP_DIR}|g" \
    -e "s|__VENV__|${VENV}|g" \
    "${APP_DIR}/cubs-hq.service.template" > "${RENDERED}"
install -m 0644 "${RENDERED}" "/etc/systemd/system/${SERVICE_NAME}"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

log "Done. Check status with:  sudo systemctl status ${SERVICE_NAME}"
