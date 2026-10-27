#!/bin/sh
# WearForge installer for Linux, macOS and Termux.
#   curl -fsSL https://raw.githubusercontent.com/dmitthedazed/wearforge/main/install.sh | sh
set -eu

REPO="dmitthedazed/wearforge"
REF="${WEARFORGE_REF:-main}"
SRC="https://github.com/$REPO/archive/refs/heads/$REF.tar.gz"

say()  { printf '\033[36m::\033[0m %s\n' "$*"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

sudo_() { if [ "$(id -u)" -eq 0 ]; then "$@"; elif have sudo; then sudo "$@"; else "$@"; fi; }

# --- dependencies: python3 + adb ---
if [ -n "${TERMUX_VERSION:-}" ] || [ -d /data/data/com.termux ]; then
    PLATFORM=termux
    have python && have adb || { say "installing python, android-tools"; pkg install -y python android-tools; }
    PY=python
    BIN_DIR="$PREFIX/bin"
    APP_DIR="$HOME/.local/share/wearforge-app"
elif [ "$(uname -s)" = Darwin ]; then
    PLATFORM=macos
    if ! have adb; then
        have brew || die "Homebrew is required: https://brew.sh"
        say "installing android-platform-tools"
        brew install --cask android-platform-tools
    fi
    have python3 || { say "installing python"; brew install python; }
    PY=python3
    BIN_DIR="$HOME/.local/bin"
    APP_DIR="$HOME/Library/Application Support/WearForge-app"
else
    PLATFORM=linux
    if ! have adb || ! have python3; then
        say "installing python3, adb"
        if   have apt-get; then sudo_ apt-get install -y python3 python3-venv adb
        elif have pacman;  then sudo_ pacman -S --needed --noconfirm python android-tools
        elif have dnf;     then sudo_ dnf install -y python3 android-tools
        elif have zypper;  then sudo_ zypper install -y python3 android-tools
        elif have apk;     then sudo_ apk add python3 android-tools
        else die "install python3 and adb with your package manager, then rerun"
        fi
    fi
    PY=python3
    BIN_DIR="$HOME/.local/bin"
    APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/wearforge-app"
fi

# --- app: isolated venv + launcher on PATH ---
say "installing wearforge ($PLATFORM)"
"$PY" -m venv "$APP_DIR/venv" || die "python venv module is missing (Debian/Ubuntu: apt install python3-venv)"
"$APP_DIR/venv/bin/python" -m pip install -q --upgrade pip
"$APP_DIR/venv/bin/python" -m pip install -q --upgrade "$SRC"

mkdir -p "$BIN_DIR"
ln -sf "$APP_DIR/venv/bin/wearforge" "$BIN_DIR/wearforge"

say "done. run: wearforge"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) printf '   add %s to your PATH first\n' "$BIN_DIR" ;;
esac
