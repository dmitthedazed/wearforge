# WearForge ⚡

[![CI](https://github.com/dmitthedazed/wearforge/actions/workflows/ci.yml/badge.svg)](https://github.com/dmitthedazed/wearforge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Platforms](https://img.shields.io/badge/platforms-Linux%20%7C%20macOS%20%7C%20Windows-informational)](#install)

**An all-in-one ADB toolkit for Wear OS — debloat, tweak, back up, and manage
your watch from the terminal.** A single interactive TUI built with
[Rich](https://github.com/Textualize/rich) and
[questionary](https://github.com/tmbo/questionary).

## Features

- **Connection & pairing manager** — wireless pairing/connect wizard for Wear OS
  3/4/5/6, USB devices, and reconnect-from-history.
- **Device diagnostics dashboard** — brand/model, Android & SDK, battery, screen
  size/density, storage, and uptime.
- **Debloating, three ways:**
  - **Quick Debloat** — curated, safety-rated catalog for Samsung Galaxy Watch
    and Google Pixel Watch / generic Wear OS.
  - **UAD-NG Auto-Debloater** — matches installed packages against the
    [Universal Android Debloater Next Generation](https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation)
    database, brand-aware.
  - **Custom Debloat** — search/filter every package on the device and select
    manually.

  In the UAD-NG and Custom selection lists, rows stay compact with a safety
  badge (`REC`/`SAFE`/`ADV`/`CARE`/`EXP`/`RISK`); press **→** to reveal the full
  description for the highlighted package and **←** to hide it again.
- **Restore / re-enable** — from local history, all disabled/uninstalled
  packages, or a manually entered package name.
- **APK sideloading & backup** — single/bulk install, extract installed APKs,
  and list Play Store vs sideloaded apps.
- **File explorer & transfer** — push/pull files to/from the watch.
- **Utilities** — display/DPI/font tweaks, audio settings, screenshots &
  screen recording, reboot options, cache clearing, and a curated optimizer.
- **Interactive ADB shell** for ad-hoc commands.

All debloat actions default to the reversible **disable** (`pm disable-user`)
rather than uninstall, and every change is logged so it can be undone from the
Restore menu.

Runs on **Linux, macOS, and Windows** — the right platform behavior (data
directory, raw keyboard input) is detected automatically at runtime.

## Requirements

- Python 3.9+
- [`adb`](https://developer.android.com/tools/adb) (Android platform-tools) on
  your `PATH`:
  - Linux: `sudo apt install adb` / `sudo pacman -S android-tools`
  - macOS: `brew install android-platform-tools`
  - Windows: `winget install Google.PlatformTools`

## Install

**With pipx (recommended, all platforms):**

```bash
pipx install git+https://github.com/dmitthedazed/wearforge.git
wearforge
```

**With pip:**

```bash
pip install git+https://github.com/dmitthedazed/wearforge.git
wearforge
```

**From source (zero-install launcher):** the bundled script creates a
virtualenv, installs dependencies, and launches the app.

```bash
# Linux / macOS
git clone https://github.com/dmitthedazed/wearforge.git
cd wearforge
./run.sh
```

```powershell
# Windows (PowerShell)
git clone https://github.com/dmitthedazed/wearforge.git
cd wearforge
.\run.ps1
```

## Usage

```bash
wearforge                              # launch the interactive menu
wearforge --device 192.168.1.42:5555   # target a specific device on startup
wearforge --update-uad                 # refresh the UAD-NG database and exit
wearforge --verbose                    # also stream debug logs to the console
```

(When running from source, substitute `./run.sh` — any arguments are forwarded.)

### Options

| Flag | Description |
| --- | --- |
| `-d`, `--device SERIAL` | Target a specific device serial / `IP:PORT` at startup. |
| `--no-auto-connect` | Don't auto-select the first connected device. |
| `--update-uad` | Update the UAD-NG package database from GitHub and exit. |
| `-v`, `--verbose` | Also print debug logs to the console (always written to the log file). |
| `--version` | Print the version and exit. |
| `-h`, `--help` | Show help and exit. |

## Wireless pairing (Wear OS)

1. **Settings → System → About Watch → Software Info**, tap the build/software
   version 7 times to unlock Developer Options.
2. **Settings → Developer Options** → enable **ADB Debugging** and
   **Wireless Debugging**.
3. **Wireless Debugging → Pair new device** to get the IP, pairing port, and
   6-digit code, then use the pairing wizard in the app.

## Data & logs

State is stored outside the working directory so the tool behaves the same from
anywhere. The location follows each OS's convention (override any of them with
the `WEARFORGE_DATA_DIR` environment variable):

| OS | Default data directory |
| --- | --- |
| Linux | `$XDG_DATA_HOME/wearforge` or `~/.local/share/wearforge` |
| macOS | `~/Library/Application Support/WearForge` |
| Windows | `%LOCALAPPDATA%\WearForge` |

It contains:

- `backups/`, `screenshots/`, `recordings/` — output folders.
- `debloated_history.json`, `connection_history.json` — local state.
- `uad_lists_cache.json` — cached UAD-NG database.
- `wearforge.log` — rotating log file (every adb failure and crash is recorded
  here; handy when filing a bug).

## Development

```bash
pip install -e ".[dev]"
pytest
```

CI runs byte-compile + tests on Linux, macOS, and Windows (Python 3.9 & 3.12)
via GitHub Actions.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the project layout, how to add a
debloat catalog entry, testing notes, and the PR workflow.

## Disclaimer

Debloating system packages can affect device functionality. Prefer **disable**
over **uninstall**, and keep the Restore menu in mind if something breaks. Use
at your own risk.

## License

[MIT](LICENSE) © Dmytrii Savin
