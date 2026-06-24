#!/usr/bin/env python3
import sys
import os
import subprocess
import json
import re
import shlex
import socket
import signal
import logging
import argparse
from logging.handlers import RotatingFileHandler
from datetime import datetime

APP_NAME = "WearForge"
APP_VERSION = "1.2.0"

# Import interactive CLI libraries
try:
    import questionary
    from questionary.prompts.common import InquirerControl
    from prompt_toolkit.keys import Keys
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.live import Live
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
except ImportError:
    print("Error: Required dependencies not found. Please run the app using './run.sh'")
    sys.exit(1)

# Import tty/termios for raw keyboard input (Linux standard library)
try:
    import tty
    import termios
except ImportError:
    # Fallback if run on a non-POSIX platform, though user OS is Linux
    tty = None
    termios = None

# Initialize Rich Console
console = Console()

logger = logging.getLogger("wearforge")


def get_data_dir():
    """Resolve a stable, writable directory for app state, independent of CWD.

    Priority: ``WEARFORGE_DATA_DIR`` env override → ``$XDG_DATA_HOME/wearforge``
    → ``~/.local/share/wearforge``. Keeping state here (instead of the current
    directory) means the tool behaves the same whether launched via ./run.sh,
    a console entry point, or from any working directory.
    """
    override = os.environ.get("WEARFORGE_DATA_DIR")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    xdg = os.environ.get("XDG_DATA_HOME")
    base = xdg if xdg else os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "wearforge")


DATA_DIR = get_data_dir()
HISTORY_FILE = os.path.join(DATA_DIR, "debloated_history.json")
CONN_HISTORY_FILE = os.path.join(DATA_DIR, "connection_history.json")
BACKUPS_DIR = os.path.join(DATA_DIR, "backups")
SCREENSHOTS_DIR = os.path.join(DATA_DIR, "screenshots")
RECORDINGS_DIR = os.path.join(DATA_DIR, "recordings")
LOG_FILE = os.path.join(DATA_DIR, "wearforge.log")


def setup_logging(verbose=False):
    """Configure file logging (always) and optional verbose console logging."""
    os.makedirs(DATA_DIR, exist_ok=True)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(message)s")
    )
    logger.addHandler(file_handler)

    if verbose:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(stream_handler)

    logger.debug("%s %s starting (data dir: %s)", APP_NAME, APP_VERSION, DATA_DIR)

# Package Catalog with metadata
CATALOG = {
    "Samsung Galaxy Watch": [
        {
            "package": "com.samsung.android.bixby.agent",
            "name": "Bixby Voice Assistant",
            "desc": "Samsung's voice assistant. Safe to disable if using Google Assistant or none.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.bixby.wakeup",
            "name": "Bixby Voice Wakeup",
            "desc": "Listens for 'Hi Bixby' hotword. Disabling saves battery.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.samsungpay.gear",
            "name": "Samsung Pay / Wallet",
            "desc": "Samsung's payment service. Safe to remove if you use Google Wallet or no watch payments.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.gallery.watch",
            "name": "Samsung Gallery",
            "desc": "Watch gallery app. Safe to remove if you do not sync or view phone photos on the watch.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.wear.voicerecorder",
            "name": "Samsung Voice Recorder",
            "desc": "Voice recorder utility. Safe to remove if you do not record voice memos on your watch.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.compass",
            "name": "Compass",
            "desc": "Compass utility app. Safe to remove if you do not use navigation/compass on watch.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.stopwatch",
            "name": "Stopwatch",
            "desc": "Samsung Stopwatch app.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.flashlight",
            "name": "Flashlight",
            "desc": "Samsung Flashlight utility.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.calendar",
            "name": "Samsung Calendar",
            "desc": "Syncs calendar events from Samsung Calendar. Safe if using Google Calendar.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.weather",
            "name": "Samsung Weather",
            "desc": "Samsung Weather widget and app. Safe if using Google Weather or none.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.aremoji",
            "name": "AR Emoji Watch Face",
            "desc": "Pre-installed AR Emoji watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.animal",
            "name": "Animal Watch Face",
            "desc": "Pre-installed Animal watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.artwork",
            "name": "Artwork Watch Face",
            "desc": "Pre-installed Artwork watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.badgeline",
            "name": "Badge Line Watch Face",
            "desc": "Pre-installed Badge Line watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.classicsection",
            "name": "Classic Section Watch Face",
            "desc": "Pre-installed Classic Section watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.livechamber",
            "name": "Live Chamber Watch Face",
            "desc": "Pre-installed Live Chamber watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.myphoto",
            "name": "My Photo Watch Face",
            "desc": "Pre-installed My Photo watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.retro",
            "name": "Retro Watch Face",
            "desc": "Pre-installed Retro watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.simpleclock",
            "name": "Simple Clock Watch Face",
            "desc": "Pre-installed Simple Clock watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.simplesection",
            "name": "Simple Section Watch Face",
            "desc": "Pre-installed Simple Section watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.typography",
            "name": "Typography Watch Face",
            "desc": "Pre-installed Typography watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.wordclock",
            "name": "Word Clock Watch Face",
            "desc": "Pre-installed Word Clock watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.supergraphic",
            "name": "Super Graphic Watch Face",
            "desc": "Pre-installed Super Graphic watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.watchface.newclassic",
            "name": "New Classic Watch Face",
            "desc": "Pre-installed New Classic watch face.",
            "safety": "Safe",
        },
        {
            "package": "com.samsung.android.watch.alarm",
            "name": "Samsung Alarm",
            "desc": "Samsung Alarm app. CAUTION: May break alarm sync unless using a third party alarm.",
            "safety": "Caution",
        },
        {
            "package": "com.samsung.android.contacts",
            "name": "Samsung Contacts",
            "desc": "Samsung Contacts. CAUTION: Disabling may cause problems syncing phone contacts to watch.",
            "safety": "Caution",
        },
    ],
    "Google Pixel Watch & Generic Wear OS": [
        {
            "package": "com.google.android.apps.maps",
            "name": "Google Maps",
            "desc": "Google Maps for navigation. Safe to remove if you navigate via phone only.",
            "safety": "Safe",
        },
        {
            "package": "com.google.android.apps.fitness",
            "name": "Google Fit",
            "desc": "Google Fit app. Safe to remove if you use Samsung Health, Fitbit, or other trackers.",
            "safety": "Safe",
        },
        {
            "package": "com.google.android.wearable.assistant",
            "name": "Google Assistant",
            "desc": "Google Voice Assistant. Safe to remove if you do not use voice assistant features.",
            "safety": "Safe",
        },
        {
            "package": "com.google.android.apps.walletnfcrel",
            "name": "Google Wallet",
            "desc": "Google Pay/Wallet. Safe to remove if you do not use NFC payments on the watch.",
            "safety": "Safe",
        },
        {
            "package": "com.google.android.youtube.music",
            "name": "YouTube Music",
            "desc": "YouTube Music player. Safe to remove if you do not use the YouTube Music watch app.",
            "safety": "Safe",
        },
        {
            "package": "com.google.android.apps.handwriting.ime",
            "name": "Google Handwriting Input",
            "desc": "Handwriting recognition keyboard. Safe if you use Gboard keyboard or voice input.",
            "safety": "Safe",
        },
        {
            "package": "com.google.android.wearable.weather",
            "name": "Google Weather",
            "desc": "Google Weather service. Safe if you do not use weather tiles/widgets.",
            "safety": "Safe",
        },
        {
            "package": "com.google.android.wearable.marvelous",
            "name": "Pixel Marvelous Faces",
            "desc": "Pre-installed Marvelous watch face pack.",
            "safety": "Safe",
        },
        {
            "package": "com.google.android.wearable.classic",
            "name": "Pixel Classic Faces",
            "desc": "Pre-installed Classic watch face pack.",
            "safety": "Safe",
        },
        {
            "package": "com.google.android.wearable.photos",
            "name": "Google Photos Face",
            "desc": "Pre-installed Photos watch face pack.",
            "safety": "Safe",
        },
        {
            "package": "com.google.android.apps.safety.wearable",
            "name": "Personal Safety",
            "desc": "Fall detection & emergency SOS. CAUTION: Disabling will turn off safety and SOS functionality.",
            "safety": "Caution",
        },
        {
            "package": "com.google.android.wearable.tts",
            "name": "Google TTS (Text-to-Speech)",
            "desc": "Voice engine. CAUTION: Needed for voice feedback in workouts, accessibility, or assistant.",
            "safety": "Caution",
        }
    ]
}

# --- State Management & Config ---
selected_device = None

# Cache of device serial -> "Brand Model" string. Brand/model are static for a
# given device, so we look them up once instead of shelling out to adb on every
# screen redraw (show_header runs on every menu).
_device_info_cache = {}

def init_workspace():
    """Create the data dir and backup/screenshot/recording folders if missing."""
    for path in (DATA_DIR, BACKUPS_DIR, SCREENSHOTS_DIR, RECORDINGS_DIR):
        os.makedirs(path, exist_ok=True)

def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json(filepath, data):
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        console.print(f"[red]Error saving file {filepath}: {e}[/red]")

# --- UAD-NG Remote Database Manager ---
UAD_URL = "https://raw.githubusercontent.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation/main/resources/assets/uad_lists.json"
UAD_CACHE_FILE = os.path.join(DATA_DIR, "uad_lists_cache.json")

def load_uad_list():
    if os.path.exists(UAD_CACHE_FILE):
        try:
            with open(UAD_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def update_uad_list():
    import urllib.request
    try:
        console.print("[yellow]Downloading latest UAD-NG package list from GitHub...[/yellow]")
        req = urllib.request.Request(
            UAD_URL,
            headers={'User-Agent': 'Mozilla/5.0 (WearOS All-in-One Debloater)'}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode('utf-8'))
            save_json(UAD_CACHE_FILE, data)
            console.print(f"[green]Successfully updated UAD database! ({len(data)} packages loaded)[/green]")
            return data
    except Exception as e:
        console.print(f"[red]Failed to download UAD list: {e}[/red]")
        console.print("[yellow]Using existing cache if available.[/yellow]")
        return load_uad_list()

def get_fallback_friendly_name(package):
    parts = package.split('.')
    skip_words = {'com', 'org', 'net', 'android', 'google', 'samsung', 'wear', 'wearable', 'apps', 'app', 'providers', 'provider', 'services', 'service', 'watch', 'watchface'}
    filtered = [w for w in parts if w.lower() not in skip_words]
    
    if not filtered:
        filtered = parts[-2:] if len(parts) >= 2 else parts
        
    words = []
    for part in filtered:
        subparts = re.split(r'[_]+', part)
        for sp in subparts:
            # Splits camelCase (e.g. voiceRecorder -> voice Recorder)
            camel_split = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', sp)
            if camel_split:
                words.extend(camel_split)
            else:
                words.append(sp)
                
    friendly_words = [w.capitalize() for w in words if w.strip()]
    friendly_name = " ".join(friendly_words)
    
    replacements = {
        "Tts": "Text-to-Speech",
        "Ime": "Keyboard/Input",
        "Nfcrel": "NFC Wallet",
        "Aremoji": "AR Emoji",
        "Gboard": "Gboard Keyboard",
        "Tty": "TTY",
        "Vos": "Voice Assistant",
    }
    for k, v in replacements.items():
        friendly_name = re.sub(r'\b' + k + r'\b', v, friendly_name)
        
    return friendly_name

def get_friendly_name(pkg, uad_data=None):
    for brand, apps in CATALOG.items():
        for app in apps:
            if app['package'] == pkg:
                return app['name']
                
    if uad_data and pkg in uad_data:
        desc = uad_data[pkg].get("description", "")
        if desc:
            first_sentence = desc.split('\n')[0].split('.')[0].split(',')[0].strip()
            if len(first_sentence) < 40 and any(keyword in first_sentence.lower() for keyword in ["app", "assistant", "keyboard", "manager", "wallet", "player", "engine", "service", "launcher", "browser", "viewer"]):
                return first_sentence
                
    return get_fallback_friendly_name(pkg)

# --- Package selection-list formatting ---
# Short, fixed-width badges so checkbox lists line up in clean columns. Maps a
# UAD "removal" rating or catalog "safety" rating to (badge, sort_priority).
# Lower priority sorts first (more actionable / safer to remove).
_REC_BADGES = {
    "recommended": ("REC ", 0),
    "safe":        ("SAFE", 0),
    "advanced":    ("ADV ", 1),
    "caution":     ("CARE", 1),
    "expert":      ("EXP ", 2),
    "unsafe":      ("RISK", 3),
}
REC_LEGEND = "[dim]REC/SAFE = safe to remove · ADV/CARE = caution · EXP/RISK = expert only · ✗ = already off[/dim]"

def rec_badge(rating):
    return _REC_BADGES.get((rating or "").strip().lower(), ("--  ", 4))

def _truncate(text, width):
    return text if len(text) <= width else text[: max(1, width - 1)] + "…"

def make_pkg_choice(pkg, friendly, rating, is_disabled, value=None, checked=False, description=None):
    """Build a compact, aligned questionary.Choice for a package-selection list.

    The compact row stays on one line; the full ``description`` (e.g. the UAD-NG
    blurb) is attached out of sight and revealed on demand via the → gesture in
    checkbox_with_info().
    """
    badge, _ = rec_badge(rating)
    line = f"{badge} │ {pkg}"
    # Append the friendly name only when it adds info beyond the package id.
    flat_friendly = (friendly or "").lower().replace(" ", "")
    if flat_friendly and flat_friendly not in pkg.lower().replace(".", ""):
        line += f"  · {friendly}"
    if is_disabled:
        line += "  ✗"
    # Keep within the terminal width so long ids never wrap or truncate mid-word.
    line = _truncate(line, max(40, console.width - 6))

    desc = None
    if description:
        desc = " ".join(str(description).split())  # collapse newlines/whitespace
        desc = _truncate(desc, 240)

    return questionary.Choice(
        title=line,
        value=value if value is not None else pkg,
        checked=checked,
        description=desc,
    )

def checkbox_with_info(message, choices, **kwargs):
    """A questionary.checkbox where the → key reveals the highlighted item's
    description (the UAD-NG / catalog blurb) and ← hides it again.

    Descriptions start hidden so the list stays compact; the gesture lets you
    "fall into" the details for whatever row the cursor is on. Falls back to a
    plain checkbox if the prompt_toolkit internals ever change shape.
    """
    kwargs.setdefault("show_description", False)
    question = questionary.checkbox(message, choices=choices, **kwargs)

    app = getattr(question, "application", None)
    if app is None or app.key_bindings is None:
        return question

    controls = [c for c in app.layout.find_all_controls() if isinstance(c, InquirerControl)]
    if not controls:
        return question
    ic = controls[0]

    @app.key_bindings.add(Keys.Right, eager=True)
    def _reveal_description(event):
        ic.show_description = True

    @app.key_bindings.add(Keys.Left, eager=True)
    def _hide_description(event):
        ic.show_description = False

    return question

def log_action_to_history(device_id, package, action, details=""):
    history = load_json(HISTORY_FILE)
    if device_id not in history:
        history[device_id] = {}
    history[device_id][package] = {
        "action": action,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "details": details
    }
    save_json(HISTORY_FILE, history)

def log_connection_to_history(device_serial, device_name):
    conn_hist = load_json(CONN_HISTORY_FILE)
    conn_hist[device_serial] = {
        "device_name": device_name,
        "last_connected": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_json(CONN_HISTORY_FILE, conn_hist)

# --- ADB Process Runners ---

def run_adb(args, device_serial=None, timeout=12):
    """Run an adb command and return exit code, stdout, and stderr."""
    cmd = ['adb']
    if device_serial:
        cmd += ['-s', device_serial]
    cmd += args
    logger.debug("adb run: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            logger.warning(
                "adb rc=%s for %s | stderr=%s",
                result.returncode, " ".join(args), result.stderr.strip(),
            )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error("adb timed out after %ss: %s", timeout, " ".join(cmd))
        return -1, "", "Command timed out"
    except FileNotFoundError:
        logger.error("adb executable not found on PATH")
        return -2, "", "adb executable not found. Please install Android Platform Tools."

def run_adb_stream(args, device_serial=None, timeout=300):
    """Run an adb command, stream stdout/stderr line by line to console, and return returncode."""
    cmd = ['adb']
    if device_serial:
        cmd += ['-s', device_serial]
    cmd += args
    try:
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in p.stdout:
            cleaned = line.strip()
            if cleaned:
                console.print(f"  [dim]{cleaned}[/dim]")
        p.wait(timeout=timeout)
        return p.returncode
    except subprocess.TimeoutExpired:
        p.kill()
        return -1
    except Exception as e:
        console.print(f"[red]Execution error: {e}[/red]")
        return -1

def pair_device(ip_port, pairing_code):
    """Executes the adb pair command and supplies the pairing code to stdin."""
    try:
        p = subprocess.Popen(
            ['adb', 'pair', ip_port],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        stdout, stderr = p.communicate(input=pairing_code + "\n", timeout=15)
        return p.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        p.kill()
        return -1, "", "Pairing process timed out."
    except Exception as e:
        return -1, "", str(e)

def get_connected_devices():
    """Queries adb devices and parses the result."""
    rc, stdout, stderr = run_adb(['devices'])
    if rc != 0:
        return []
    devices = []
    lines = stdout.splitlines()
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2:
            serial, state = parts[0], parts[1]
            devices.append({"serial": serial, "state": state})
    return devices

def get_device_info(device_serial):
    """Gets device model and brand info, cached per serial to avoid repeated adb calls."""
    if device_serial in _device_info_cache:
        return _device_info_cache[device_serial]

    rc_brand, brand, _ = run_adb(['shell', 'getprop', 'ro.product.brand'], device_serial)
    rc_model, model, _ = run_adb(['shell', 'getprop', 'ro.product.model'], device_serial)

    brand = brand.strip().capitalize() if rc_brand == 0 and brand.strip() else "Unknown"
    model = model.strip() if rc_model == 0 and model.strip() else "Unknown Device"
    info = f"{brand} {model}"

    # Only cache real lookups so a transient failure (e.g. device asleep) isn't sticky.
    if brand != "Unknown" or model != "Unknown Device":
        _device_info_cache[device_serial] = info
    return info

def get_device_packages(device_serial):
    """Fetches packages from device and groups them by active, disabled, and uninstalled."""
    # List active packages
    rc, stdout, _ = run_adb(['shell', 'pm', 'list', 'packages'], device_serial)
    if rc != 0:
        return None
    
    active_packages = set()
    for line in stdout.splitlines():
        if line.startswith('package:'):
            active_packages.add(line.split(':', 1)[1].strip())
            
    # List disabled packages
    rc, stdout, _ = run_adb(['shell', 'pm', 'list', 'packages', '-d'], device_serial)
    disabled_packages = set()
    if rc == 0:
        for line in stdout.splitlines():
            if line.startswith('package:'):
                disabled_packages.add(line.split(':', 1)[1].strip())
                
    # List uninstalled packages (for user 0)
    rc, stdout, _ = run_adb(['shell', 'pm', 'list', 'packages', '-u'], device_serial)
    uninstalled_packages = set()
    if rc == 0:
        for line in stdout.splitlines():
            if line.startswith('package:'):
                pkg = line.split(':', 1)[1].strip()
                if pkg not in active_packages:
                    uninstalled_packages.add(pkg)
                    
    return {
        "active": sorted(list(active_packages - disabled_packages)),
        "disabled": sorted(list(disabled_packages)),
        "uninstalled": sorted(list(uninstalled_packages))
    }

def suggest_subnet():
    """Helper to guess the local subnet for IP suggestion."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}."
    except Exception:
        pass
    return "192.168.1."

# --- Helper for Single Keyboard Keypress ---
def getch():
    """Reads a single keypress from standard input in raw terminal mode."""
    if not tty or not termios:
        return sys.stdin.read(1)
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

# --- Screens & UI Setup ---

def show_header(subtitle=""):
    console.clear()
    line = f"[bold cyan]⚡ {APP_NAME}[/bold cyan]"
    if subtitle:
        line += f"  [dim]›[/dim] [yellow]{subtitle}[/yellow]"
    if selected_device:
        line += f"   [green]{get_device_info(selected_device)}[/green] [dim]({selected_device})[/dim]"
    else:
        line += "   [red]● no device[/red]"
    console.print(line)
    console.rule(style="cyan")

# --- Feature Modules ---

# 1. CONNECTION MANAGER
def select_device_menu():
    global selected_device
    show_header("Connection & Pairing Manager")
    
    devices = get_connected_devices()
    
    table = Table(title="Connected USB / Network ADB Devices")
    table.add_column("Index", style="cyan")
    table.add_column("Serial / IP:Port", style="green")
    table.add_column("State", style="yellow")
    table.add_column("Device Info", style="blue")
    
    choices = []
    for idx, d in enumerate(devices):
        info = get_device_info(d['serial']) if d['state'] == 'device' else "N/A"
        table.add_row(str(idx + 1), d['serial'], d['state'], info)
        choices.append(f"Use: {d['serial']} ({info})")
        
    console.print(table)
    
    # Load connection history
    conn_history = load_json(CONN_HISTORY_FILE)
    if conn_history:
        console.print("\n[cyan]Previously Connected Devices (History):[/cyan]")
        for serial, details in conn_history.items():
            console.print(f"  • [green]{serial}[/green] - {details.get('device_name')} (Last: {details.get('last_connected')})")
            # Only add to choices if not currently active to prevent duplicates
            if not any(d['serial'] == serial for d in devices):
                choices.append(f"Reconnect to: {serial} ({details.get('device_name')})")

    choices.extend([
        "Pair a new Wear OS Watch wirelessly",
        "Connect to a watch via IP:Port",
        "Refresh Devices list",
        "Disconnect all ADB devices",
        "Go back to Main Menu"
    ])
    
    selection = questionary.select(
        "Select an action:",
        choices=choices
    ).ask()
    
    if not selection or selection == "Go back to Main Menu":
        return
        
    if selection == "Refresh Devices list":
        select_device_menu()
    elif selection == "Disconnect all ADB devices":
        console.print("[yellow]Disconnecting all adb devices...[/yellow]")
        run_adb(['disconnect'])
        selected_device = None
        questionary.press_any_key_to_continue().ask()
    elif selection == "Pair a new Wear OS Watch wirelessly":
        pair_wizard()
    elif selection == "Connect to a watch via IP:Port":
        connect_wizard()
    elif selection.startswith("Reconnect to: "):
        serial = selection.split("Reconnect to: ")[1].split(" (")[0]
        console.print(f"[yellow]Attempting reconnection to {serial}...[/yellow]")
        rc, stdout, stderr = run_adb(['connect', serial])
        if rc == 0 and "connected" in stdout.lower():
            selected_device = serial
            log_connection_to_history(selected_device, get_device_info(selected_device))
            console.print(f"[green]Successfully reconnected to {selected_device}![/green]")
        else:
            console.print(f"[red]Reconnection failed: {stdout or stderr}[/red]")
        questionary.press_any_key_to_continue().ask()
    elif selection.startswith("Use: "):
        serial = selection.split("Use: ")[1].split(" (")[0]
        device_state = next((d['state'] for d in devices if d['serial'] == serial), None)
        if device_state == 'unauthorized':
            console.print("[red]Error: Device is unauthorized. Look at your watch screen and accept debugging permissions.[/red]")
            questionary.press_any_key_to_continue().ask()
        else:
            selected_device = serial
            log_connection_to_history(selected_device, get_device_info(selected_device))
            console.print(f"[green]Successfully targeted device: {selected_device}[/green]")
            questionary.press_any_key_to_continue().ask()

def pair_wizard():
    show_header("Wireless Pairing (Wear OS 3/4/5/6)")
    console.print("[dim]Watch:[/dim] Settings › About › tap [bold]Software Version[/bold] ×7 → [bold]Developer Options[/bold]")
    console.print("[dim]Enable[/dim] ADB + Wireless Debugging → [bold]Pair new device[/bold] → note IP:port & 6-digit code\n")
    
    suggest = suggest_subnet()
    ip_port = questionary.text(
        "Enter IP & Pairing Port (format: IP:PORT):",
        default=suggest,
        validate=lambda text: True if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$', text.strip()) else "Format must be IP:PORT"
    ).ask()
    
    if not ip_port:
        return
        
    pairing_code = questionary.text(
        "Enter 6-digit Pairing Code:",
        validate=lambda text: True if len(text.strip()) == 6 and text.strip().isdigit() else "Please enter a 6-digit number"
    ).ask()
    
    if not pairing_code:
        return
        
    console.print("\n[yellow]Executing adb pair...[/yellow]")
    rc, stdout, stderr = pair_device(ip_port.strip(), pairing_code.strip())
    
    if rc == 0 and "successfully paired" in stdout.lower():
        console.print(f"[green]Successfully paired! {stdout.strip()}[/green]")
        console.print("\nNow open the main [bold]Wireless Debugging[/bold] screen on your watch again.")
        console.print("Note the IP and the [bold]Connection Port[/bold] (usually different from pairing port).")
        if questionary.confirm("Connect to the watch now?").ask():
            connect_wizard(default_ip=ip_port.split(':')[0])
    else:
        console.print(f"[red]Pairing Failed.[/red]")
        console.print(f"Stdout: {stdout}\nStderr: {stderr}")
        questionary.press_any_key_to_continue().ask()

def connect_wizard(default_ip=""):
    show_header("Wireless Connection Wizard")
    suggest = default_ip if default_ip else suggest_subnet()
    
    ip_port = questionary.text(
        "Enter Watch IP & Connection Port (IP:PORT):",
        default=suggest if default_ip else f"{suggest}:5555",
        validate=lambda text: True if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$', text.strip()) else "Format must be IP:PORT"
    ).ask()
    
    if not ip_port:
        return
        
    console.print(f"\n[yellow]Connecting to {ip_port}...[/yellow]")
    rc, stdout, stderr = run_adb(['connect', ip_port.strip()])
    
    if rc == 0 and "connected to" in stdout.lower():
        global selected_device
        selected_device = ip_port.strip()
        log_connection_to_history(selected_device, get_device_info(selected_device))
        console.print(f"[green]Successfully connected to {selected_device}![/green]")
    else:
        console.print(f"[red]Connection Failed: {stdout.strip() or stderr.strip()}[/red]")
        
    questionary.press_any_key_to_continue().ask()

# 2. DEVICE SPECS DASHBOARD
def show_device_dashboard():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    show_header("Watch System Specification Dashboard")
    
    with console.status("[yellow]Fetching system properties...[/yellow]"):
        _, brand, _ = run_adb(['shell', 'getprop', 'ro.product.brand'], selected_device)
        _, model, _ = run_adb(['shell', 'getprop', 'ro.product.model'], selected_device)
        _, android_ver, _ = run_adb(['shell', 'getprop', 'ro.build.version.release'], selected_device)
        _, sdk_ver, _ = run_adb(['shell', 'getprop', 'ro.build.version.sdk'], selected_device)
        _, serial, _ = run_adb(['shell', 'getprop', 'ro.serialno'], selected_device)
        _, cpu_abi, _ = run_adb(['shell', 'getprop', 'ro.product.cpu.abi'], selected_device)
        
        # Battery details
        _, battery_out, _ = run_adb(['shell', 'dumpsys', 'battery'], selected_device)
        bat_level = "Unknown"
        bat_status = "Unknown"
        for line in battery_out.splitlines():
            if "level:" in line:
                bat_level = f"{line.split(':')[1].strip()}%"
            if "status:" in line:
                status_code = line.split(':')[1].strip()
                status_map = {"1": "Unknown", "2": "Charging", "3": "Discharging", "4": "Not Charging", "5": "Full"}
                bat_status = status_map.get(status_code, f"Code {status_code}")
                
        # Screen details
        _, size_out, _ = run_adb(['shell', 'wm', 'size'], selected_device)
        screen_size = size_out.replace("Physical size:", "").replace("Override size:", "-> Override:").strip()
        
        _, dens_out, _ = run_adb(['shell', 'wm', 'density'], selected_device)
        screen_density = dens_out.replace("Physical density:", "").replace("Override density:", "-> Override:").strip()
        
        # Storage details
        _, df_out, _ = run_adb(['shell', 'df', '-h', '/data'], selected_device)
        storage_info = "N/A"
        for line in df_out.splitlines():
            if "/data" in line:
                parts = line.split()
                if len(parts) >= 5:
                    storage_info = f"Size: {parts[1]} | Used: {parts[2]} ({parts[4]}) | Free: {parts[3]}"
                    
        # Uptime
        _, uptime_out, _ = run_adb(['shell', 'cat', '/proc/uptime'], selected_device)
        try:
            uptime_sec = float(uptime_out.split()[0])
            hours = int(uptime_sec // 3600)
            minutes = int((uptime_sec % 3600) // 60)
            uptime_str = f"{hours}h {minutes}m"
        except Exception:
            uptime_str = "Unknown"

    table = Table(show_header=False, box=None)
    table.add_row("[bold cyan]Brand & Model:[/bold cyan]", f"{brand.strip().capitalize()} {model.strip()}")
    table.add_row("[bold cyan]Android / SDK:[/bold cyan]", f"Android {android_ver.strip()} (SDK {sdk_ver.strip()})")
    table.add_row("[bold cyan]Serial Number:[/bold cyan]", serial.strip())
    table.add_row("[bold cyan]CPU Architecture:[/bold cyan]", cpu_abi.strip())
    table.add_row("[bold cyan]Battery Level:[/bold cyan]", f"{bat_level} ({bat_status})")
    table.add_row("[bold cyan]Screen Size:[/bold cyan]", screen_size)
    table.add_row("[bold cyan]Screen Density:[/bold cyan]", screen_density)
    table.add_row("[bold cyan]Storage Info:[/bold cyan]", storage_info)
    table.add_row("[bold cyan]Uptime:[/bold cyan]", uptime_str)
    
    console.print(Panel(table, title="System Diagnostics Information", border_style="green"))
    questionary.press_any_key_to_continue().ask()

# 3. FILE EXPLORER & TRANSFER
def file_explorer_menu():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    show_header("File Transfer Manager")
    
    choice = questionary.select(
        "Select file operation:",
        choices=[
            "Upload file to Watch (PC -> Watch)",
            "Download file from Watch (Watch -> PC)",
            "Go Back"
        ]
    ).ask()
    
    if not choice or choice == "Go Back":
        return
        
    if "Upload file to Watch" in choice:
        local_path = questionary.text("Enter local file path on PC:").ask()
        if not local_path or not os.path.exists(local_path):
            console.print("[red]Error: Local file does not exist![/red]")
            questionary.press_any_key_to_continue().ask()
            return
            
        filename = os.path.basename(local_path)
        dest_choices = [
            "/sdcard/Download/",
            "/sdcard/Music/",
            "/sdcard/Pictures/",
            "/sdcard/"
        ]
        dest_dir = questionary.select("Select target folder on watch:", choices=dest_choices).ask()
        if not dest_dir:
            return
            
        dest_path = os.path.join(dest_dir, filename)
        
        console.print(f"[yellow]Uploading {local_path} to {dest_path}...[/yellow]")
        rc, stdout, stderr = run_adb(['push', local_path, dest_path], selected_device)
        if rc == 0:
            console.print(f"[green]Success: File uploaded successfully![/green]")
            # Trigger media scan for sounds/images
            run_adb(['shell', 'am', 'broadcast', '-a', 'android.intent.action.MEDIA_SCANNER_SCAN_FILE', '-d', f'file://{dest_path}'], selected_device)
        else:
            console.print(f"[red]Upload failed: {stderr or stdout}[/red]")
        questionary.press_any_key_to_continue().ask()
        
    elif "Download file from Watch" in choice:
        watch_path = questionary.text("Enter full watch file path (e.g. /sdcard/Music/song.mp3):").ask()
        if not watch_path:
            return
            
        local_dir = questionary.text("Enter local folder on PC to save (default: current folder):", default=".").ask()
        
        console.print(f"[yellow]Downloading {watch_path} to {local_dir}...[/yellow]")
        rc, stdout, stderr = run_adb(['pull', watch_path, local_dir], selected_device)
        if rc == 0:
            console.print(f"[green]Success: File pulled successfully to {local_dir}![/green]")
        else:
            console.print(f"[red]Download failed: {stderr or stdout}[/red]")
        questionary.press_any_key_to_continue().ask()

# 4. SIDELOADING & BACKUPS
def get_installer_name(package, device_serial):
    """Retrieves the installer package for verification of source (Play store vs sideloaded)."""
    rc, stdout, _ = run_adb(['shell', 'pm', 'get-installer-package-name', package], device_serial)
    if rc == 0:
        # Format might be 'Installer: com.android.vending'
        for line in stdout.splitlines():
            if "installer" in line.lower():
                val = line.split(":")[-1].strip()
                return val if val != "null" else "Sideloaded/Pre-installed"
    return "Unknown"

def apk_manager_menu():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    show_header("Application Sideloading & Backup Manager")
    
    choice = questionary.select(
        "Select Operation:",
        choices=[
            "Sideload single APK (Install)",
            "Sideload bulk APKs from folder",
            "Extract & Backup Watch applications (Extract APKs)",
            "Restore backed-up APKs (Bulk Install)",
            "List User Apps (Filter Play Store vs Sideloaded)",
            "Go Back"
        ]
    ).ask()
    
    if not choice or choice == "Go Back":
        return
        
    init_workspace()
    
    if "Sideload single APK" in choice:
        apk_path = questionary.text("Enter local path to APK file:").ask()
        if not apk_path or not os.path.exists(apk_path) or not apk_path.endswith('.apk'):
            console.print("[red]Error: Invalid file path or not an APK.[/red]")
            questionary.press_any_key_to_continue().ask()
            return
        console.print(f"[yellow]Sideloading {apk_path}...[/yellow]")
        rc, stdout, stderr = run_adb(['install', '-r', apk_path], selected_device)
        if rc == 0:
            console.print("[green]Sideload installation successful![/green]")
        else:
            console.print(f"[red]Installation failed: {stderr or stdout}[/red]")
        questionary.press_any_key_to_continue().ask()
        
    elif "Sideload bulk APKs" in choice:
        apk_folder = questionary.text("Enter local folder path containing APK files:").ask()
        if not apk_folder or not os.path.exists(apk_folder):
            console.print("[red]Error: Folder does not exist![/red]")
            questionary.press_any_key_to_continue().ask()
            return
            
        apks = [os.path.join(apk_folder, f) for f in os.listdir(apk_folder) if f.endswith('.apk')]
        if not apks:
            console.print("[yellow]No APK files found in this directory.[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
            
        console.print(f"[cyan]Found {len(apks)} APK files. Starting bulk install...[/cyan]\n")
        success, failed = 0, 0
        for apk in apks:
            console.print(f"Installing {os.path.basename(apk)}... ", end="")
            rc, _, _ = run_adb(['install', '-r', apk], selected_device)
            if rc == 0:
                console.print("[green]OK[/green]")
                success += 1
            else:
                console.print("[red]FAILED[/red]")
                failed += 1
                
        console.print(f"\n[green]Bulk Install Finished! Success: {success}, Failed: {failed}[/green]")
        questionary.press_any_key_to_continue().ask()
        
    elif "Extract & Backup Watch applications" in choice:
        console.print("[yellow]Querying packages on the watch...[/yellow]")
        pkg_status = get_device_packages(selected_device)
        if not pkg_status:
            console.print("[red]Failed to fetch packages.[/red]")
            questionary.press_any_key_to_continue().ask()
            return
            
        all_pkgs = sorted(pkg_status['active'])
        uad_data = load_uad_list()
        choices = []
        for p in all_pkgs:
            friendly = get_friendly_name(p, uad_data)
            choices.append(questionary.Choice(title=f"{friendly} ({p})", value=p))
            
        selected_pkgs = questionary.checkbox(
            "Select packages to backup / extract APKs (Space to select, Enter to confirm):",
            choices=choices
        ).ask()
        
        if not selected_pkgs:
            return
            
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        console.print(f"\n[cyan]Extracting {len(selected_pkgs)} packages to {BACKUPS_DIR}...[/cyan]\n")
        success, failed = 0, 0
        for pkg in selected_pkgs:
            friendly = get_friendly_name(pkg, uad_data)
            console.print(f"Extracting: [cyan]{friendly}[/cyan] ({pkg})... ", end="")
            rc, stdout, _ = run_adb(['shell', 'pm', 'path', pkg], selected_device)
            if rc == 0 and "package:" in stdout:
                apk_path = stdout.split("package:")[-1].strip()
                local_dest = os.path.join(BACKUPS_DIR, f"{pkg}.apk")
                rc_pull, _, _ = run_adb(['pull', apk_path, local_dest], selected_device)
                if rc_pull == 0:
                    console.print("[green]OK[/green]")
                    success += 1
                else:
                    console.print("[red]FAILED to pull[/red]")
                    failed += 1
            else:
                console.print("[red]FAILED to locate path[/red]")
                failed += 1
                
        console.print(f"\n[green]Backup Finished! Saved in {BACKUPS_DIR}. Success: {success}, Failed: {failed}[/green]")
        questionary.press_any_key_to_continue().ask()

    elif "Restore backed-up APKs" in choice:
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        apks = [f for f in os.listdir(BACKUPS_DIR) if f.endswith('.apk')]
        if not apks:
            console.print(f"[yellow]No backups found in {BACKUPS_DIR}.[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
            
        uad_data = load_uad_list()
        choices = []
        for a in apks:
            pkg = a.replace('.apk', '')
            friendly = get_friendly_name(pkg, uad_data)
            choices.append(questionary.Choice(title=f"{friendly} ({a})", value=a))
            
        selected_apks = questionary.checkbox(
            "Select APK backups to restore / reinstall (Space to select, Enter to confirm):",
            choices=choices
        ).ask()
        
        if not selected_apks:
            return
            
        console.print(f"\n[cyan]Restoring {len(selected_apks)} packages...[/cyan]\n")
        success, failed = 0, 0
        for apk in selected_apks:
            pkg = apk.replace('.apk', '')
            friendly = get_friendly_name(pkg, uad_data)
            local_apk = os.path.join(BACKUPS_DIR, apk)
            console.print(f"Restoring [cyan]{friendly}[/cyan] ({apk})... ", end="")
            rc, _, _ = run_adb(['install', '-r', local_apk], selected_device)
            if rc == 0:
                console.print("[green]OK[/green]")
                success += 1
            else:
                console.print("[red]FAILED[/red]")
                failed += 1
                
        console.print(f"\n[green]Restore Finished! Success: {success}, Failed: {failed}[/green]")
        questionary.press_any_key_to_continue().ask()
        
    elif "List User Apps" in choice:
        # Lists third party apps only, and gets installer package
        console.print("[yellow]Fetching user applications list...[/yellow]")
        rc, stdout, _ = run_adb(['shell', 'pm', 'list', 'packages', '-3'], selected_device)
        if rc != 0:
            console.print("[red]Failed to fetch user packages.[/red]")
            questionary.press_any_key_to_continue().ask()
            return
            
        packages = []
        for line in stdout.splitlines():
            if line.startswith('package:'):
                packages.append(line.split(':', 1)[1].strip())
                
        if not packages:
            console.print("[yellow]No user-installed applications found on the watch.[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
            
        play_store_apps = []
        sideload_apps = []
        
        # Use live progress spinner
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("[yellow]Analyzing package installer sources...[/yellow]", total=len(packages))
            for pkg in packages:
                src = get_installer_name(pkg, selected_device)
                if "vending" in src or "play" in src.lower():
                    play_store_apps.append(pkg)
                else:
                    sideload_apps.append((pkg, src))
                progress.advance(task)
                
        # Draw tables
        play_table = Table(title="Apps Installed from Google Play Store", border_style="green")
        play_table.add_column("Package Name", style="green")
        for p in play_store_apps:
            play_table.add_row(p)
            
        side_table = Table(title="Apps Sideloaded / Pre-installed (Outside Play Store)", border_style="yellow")
        side_table.add_column("Package Name", style="yellow")
        side_table.add_column("Installer Package", style="cyan")
        for p, src in sideload_apps:
            side_table.add_row(p, src)
            
        console.print(play_table)
        console.print("")
        console.print(side_table)
        questionary.press_any_key_to_continue().ask()

# 5. DISPLAY & CUSTOMIZATION
def display_settings_menu():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    show_header("Display & Interface Settings")
    
    choice = questionary.select(
        "Select parameter to modify:",
        choices=[
            "Change Screen Density (DPI)",
            "Change Font Size Scale",
            "Change Screen Timeout",
            "Go Back"
        ]
    ).ask()
    
    if not choice or choice == "Go Back":
        return
        
    if "Change Screen Density" in choice:
        rc, stdout, _ = run_adb(['shell', 'wm', 'density'], selected_device)
        console.print(f"[cyan]Current screen density status: {stdout.strip()}[/cyan]")
        
        dpi_val = questionary.text("Enter custom DPI value (integer, e.g. 200, 240, 320) or 'reset':").ask()
        if not dpi_val:
            return
            
        if dpi_val.lower() == 'reset':
            rc_set, _, _ = run_adb(['shell', 'wm', 'density', 'reset'], selected_device)
        else:
            if not dpi_val.isdigit():
                console.print("[red]Error: Must be a positive integer.[/red]")
                questionary.press_any_key_to_continue().ask()
                return
            rc_set, _, _ = run_adb(['shell', 'wm', 'density', dpi_val.strip()], selected_device)
            
        if rc_set == 0:
            console.print("[green]Screen density updated successfully![/green]")
        else:
            console.print("[red]Failed to update density.[/red]")
        questionary.press_any_key_to_continue().ask()
        
    elif "Change Font Size Scale" in choice:
        rc, stdout, _ = run_adb(['shell', 'settings', 'get', 'system', 'font_scale'], selected_device)
        console.print(f"[cyan]Current font scale: {stdout.strip()}[/cyan]")
        
        font_choices = [
            "0.85 (Small)",
            "1.00 (Normal / Default)",
            "1.15 (Large)",
            "1.30 (Extra Large)",
            "Custom Value"
        ]
        font_sel = questionary.select("Select font size scale:", choices=font_choices).ask()
        if not font_sel:
            return
            
        if "Custom" in font_sel:
            font_scale = questionary.text("Enter float value (e.g. 0.9, 1.2):").ask()
        else:
            font_scale = font_sel.split()[0]
            
        if not font_scale:
            return
            
        rc_set, _, _ = run_adb(['shell', 'settings', 'put', 'system', 'font_scale', font_scale.strip()], selected_device)
        if rc_set == 0:
            console.print("[green]Font scale updated successfully![/green]")
        else:
            console.print("[red]Failed to update font scale.[/red]")
        questionary.press_any_key_to_continue().ask()
        
    elif "Change Screen Timeout" in choice:
        rc, stdout, _ = run_adb(['shell', 'settings', 'get', 'system', 'screen_off_timeout'], selected_device)
        try:
            curr_ms = int(stdout.strip())
            curr_sec = curr_ms // 1000
            console.print(f"[cyan]Current Screen Timeout: {curr_sec} seconds[/cyan]")
        except Exception:
            console.print(f"[cyan]Current Screen Timeout Raw: {stdout.strip()} ms[/cyan]")
            
        timeout_choices = [
            "15 seconds (15000 ms)",
            "30 seconds (30000 ms)",
            "1 minute (60000 ms)",
            "5 minutes (300000 ms)",
            "10 minutes (600000 ms)",
            "Custom milliseconds"
        ]
        timeout_sel = questionary.select("Select screen timeout:", choices=timeout_choices).ask()
        if not timeout_sel:
            return
            
        if "Custom" in timeout_sel:
            ms_val = questionary.text("Enter duration in milliseconds:").ask()
        else:
            # Extract number inside parentheses
            ms_val = re.findall(r'\((\d+)\s*ms\)', timeout_sel)[0]
            
        if not ms_val or not ms_val.isdigit():
            console.print("[red]Error: Invalid milliseconds value.[/red]")
            questionary.press_any_key_to_continue().ask()
            return
            
        rc_set, _, _ = run_adb(['shell', 'settings', 'put', 'system', 'screen_off_timeout', ms_val], selected_device)
        if rc_set == 0:
            console.print("[green]Screen timeout updated successfully![/green]")
        else:
            console.print("[red]Failed to update screen timeout.[/red]")
        questionary.press_any_key_to_continue().ask()

# 6. AUDIO & SOUNDS
def audio_manager_menu():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    show_header("Audio & Sound Settings")
    
    choice = questionary.select(
        "Choose an option:",
        choices=[
            "Change Alert Volume levels",
            "Mute / Unmute all sound streams",
            "Upload Custom Ringtone / Alert Sound",
            "Go Back"
        ]
    ).ask()
    
    if not choice or choice == "Go Back":
        return
        
    streams = {
        "Ring (Ringtone)": "2",
        "Media (Music/Games)": "3",
        "Alarm": "4",
        "Notification": "5"
    }
    
    if "Change Alert Volume levels" in choice:
        stream_name = questionary.select("Select stream to modify:", choices=list(streams.keys())).ask()
        if not stream_name:
            return
        stream_id = streams[stream_name]
        
        vol_level = questionary.select(
            f"Select volume level for {stream_name} (0 = Muted, 15 = Loudest):",
            choices=[str(i) for i in range(16)]
        ).ask()
        
        if not vol_level:
            return
            
        # cmd audio set-stream-volume <stream> <index>
        rc, _, _ = run_adb(['shell', 'cmd', 'audio', 'set-stream-volume', stream_id, vol_level], selected_device)
        if rc == 0:
            console.print(f"[green]{stream_name} volume updated to {vol_level}![/green]")
        else:
            console.print("[red]Failed to set volume index.[/red]")
        questionary.press_any_key_to_continue().ask()
        
    elif "Mute / Unmute all sound streams" in choice:
        mute_choice = questionary.select("Select action:", choices=["Mute All Stream Volumes", "Unmute All (Set to Half)"]).ask()
        if not mute_choice:
            return
            
        val = "0" if "Mute" in mute_choice else "7"
        console.print("[yellow]Updating volume configurations...[/yellow]")
        for name, sid in streams.items():
            run_adb(['shell', 'cmd', 'audio', 'set-stream-volume', sid, val], selected_device)
        console.print(f"[green]All audio streams set to volume level {val}![/green]")
        questionary.press_any_key_to_continue().ask()
        
    elif "Upload Custom Ringtone" in choice:
        local_file = questionary.text("Enter path to custom audio file on PC (.mp3, .ogg, .wav):").ask()
        if not local_file or not os.path.exists(local_file):
            console.print("[red]Error: Local file does not exist![/red]")
            questionary.press_any_key_to_continue().ask()
            return
            
        dest_folder = questionary.select(
            "Select sound alert type:",
            choices=[
                "Ringtone (/sdcard/Ringtones/)",
                "Notification Alert (/sdcard/Notifications/)",
                "Alarm Sound (/sdcard/Alarms/)"
            ]
        ).ask()
        
        if not dest_folder:
            return
            
        dest_path = "/sdcard/Ringtones/" if "Ringtone" in dest_folder else (
            "/sdcard/Notifications/" if "Notification" in dest_folder else "/sdcard/Alarms/"
        )
        
        filename = os.path.basename(local_file)
        full_dest = os.path.join(dest_path, filename)
        
        console.print(f"[yellow]Uploading custom sound...[/yellow]")
        rc, _, _ = run_adb(['push', local_file, full_dest], selected_device)
        if rc == 0:
            # Trigger media store update
            run_adb(['shell', 'am', 'broadcast', '-a', 'android.intent.action.MEDIA_SCANNER_SCAN_FILE', '-d', f'file://{full_dest}'], selected_device)
            console.print(f"[green]Success! Sound file uploaded to watch at {full_dest}[/green]")
            console.print("You can now select it in the sound options directly on the watch settings menu.")
        else:
            console.print("[red]Failed to push audio file.[/red]")
        questionary.press_any_key_to_continue().ask()

# 7. INTERACTIVE INPUTS
def interact_tools_menu():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    show_header("Watch Input & Control Center")
    
    choice = questionary.select(
        "Select Interaction Mode:",
        choices=[
            "Launch Watch Screen Viewer (ScrCpy)",
            "Send text from PC to active input field",
            "Use PC Keyboard to type on the watch (Real-Time)",
            "Go Back"
        ]
    ).ask()
    
    if not choice or choice == "Go Back":
        return
        
    if "ScrCpy" in choice:
        console.print("[yellow]Verifying if 'scrcpy' is installed on host...[/yellow]")
        # Check command
        try:
            p = subprocess.run(['scrcpy', '--version'], capture_output=True, text=True)
            scrcpy_ok = (p.returncode == 0 or p.returncode == 1) # scrcpy can return 1 on help/version info
        except FileNotFoundError:
            scrcpy_ok = False
            
        if not scrcpy_ok:
            console.print("[red]Error: 'scrcpy' executable was not found on your system PATH.[/red]")
            console.print("ScrCpy is required to mirror and control the watch interface.")
            console.print("How to install:")
            console.print("  - Arch Linux:  [cyan]sudo pacman -S scrcpy[/cyan]")
            console.print("  - Ubuntu/Debian: [cyan]sudo apt install scrcpy[/cyan]")
            console.print("  - Fedora:      [cyan]sudo dnf install scrcpy[/cyan]")
        else:
            console.print(f"[green]Launching ScrCpy screen mirror for watch: {selected_device}...[/green]")
            # Launch in background
            subprocess.Popen(['scrcpy', '-s', selected_device, '--window-title', f"WearOS: {selected_device}"])
            console.print("[green]ScrCpy window launched successfully![/green]")
            
        questionary.press_any_key_to_continue().ask()
        
    elif "Send text from PC" in choice:
        msg = questionary.text("Enter text to send to watch active textbox:").ask()
        if msg:
            # Escape symbols
            escaped = msg.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
            rc, _, _ = run_adb(['shell', 'input', 'text', f'"{escaped}"'], selected_device)
            if rc == 0:
                console.print("[green]Text sent successfully![/green]")
            else:
                console.print("[red]Failed to send text keys.[/red]")
            questionary.press_any_key_to_continue().ask()
            
    elif "Use PC Keyboard" in choice:
        if not tty or not termios:
            console.print("[red]Real-time raw keypress listeners are not supported on this platform console.[/red]")
            questionary.press_any_key_to_continue().ask()
            return
            
        start_live_typing(selected_device)
        questionary.press_any_key_to_continue().ask()

def start_live_typing(device_serial):
    show_header("Real-Time Keyboard Input Redirector")
    console.print(Panel(
        "[bold green]Raw Keyboard Mirroring Active![/bold green]\n"
        "Characters you type here are redirected instantly to the active text field on the watch.\n\n"
        "[cyan]Controls:[/cyan]\n"
        "  • [bold]Alphanumeric / symbols[/bold] -> Type text keys\n"
        "  • [bold]Spacebar[/bold]              -> Send space character\n"
        "  • [bold]Backspace / Del[/bold]       -> Delete character (keyevent 67)\n"
        "  • [bold]Enter[/bold]                 -> Submit / Linefeed (keyevent 66)\n"
        "  • [bold]Escape Key (Esc)[/bold]       -> Exit keyboard typing mirror mode",
        border_style="yellow"
    ))
    
    try:
        while True:
            ch = getch()
            # Escape key check (\x1b)
            if ch == '\x1b':
                console.print("\n[yellow]Exit signal received. Terminating Keyboard redirection...[/yellow]")
                break
            # Backspace (\x7f or \x08)
            elif ch in ('\x7f', '\x08'):
                run_adb(['shell', 'input', 'keyevent', '67'], device_serial)
            # Enter (\r or \n)
            elif ch in ('\r', '\n'):
                run_adb(['shell', 'input', 'keyevent', '66'], device_serial)
            # Space
            elif ch == ' ':
                run_adb(['shell', 'input', 'keyevent', '62'], device_serial)
            # Standard ASCII printable character
            elif ch.isprintable():
                escaped = ch.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
                run_adb(['shell', 'input', 'text', f'"{escaped}"'], device_serial)
    except Exception as e:
        console.print(f"[red]Redirection error: {e}[/red]")

# 8. SCREEN CAPTURE UTILITIES
def screen_capture_menu():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    show_header("Watch Screen Capture Utilities")
    
    choice = questionary.select(
        "Choose capture operation:",
        choices=[
            "Take Screenshot (Save to PC)",
            "Record Screen Video (Save to PC)",
            "Go Back"
        ]
    ).ask()
    
    if not choice or choice == "Go Back":
        return
        
    init_workspace()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if "Take Screenshot" in choice:
        dest_file = os.path.join(SCREENSHOTS_DIR, f"screenshot_{timestamp}.png")
        console.print("[yellow]Capturing watch screen...[/yellow]")
        
        # screencap
        rc, _, _ = run_adb(['shell', 'screencap', '-p', '/sdcard/temp_screenshot.png'], selected_device)
        if rc == 0:
            console.print("[yellow]Downloading image file...[/yellow]")
            rc_pull, _, _ = run_adb(['pull', '/sdcard/temp_screenshot.png', dest_file], selected_device)
            run_adb(['shell', 'rm', '/sdcard/temp_screenshot.png'], selected_device)
            
            if rc_pull == 0:
                console.print(f"[green]Success: Screenshot saved to: {dest_file}[/green]")
            else:
                console.print("[red]Failed to pull image file.[/red]")
        else:
            console.print("[red]Failed to execute screenshot on device.[/red]")
        questionary.press_any_key_to_continue().ask()
        
    elif "Record Screen Video" in choice:
        dest_file = os.path.join(RECORDINGS_DIR, f"recording_{timestamp}.mp4")
        
        limit = questionary.text("Enter max recording duration in seconds (1-180, default 30):", default="30").ask()
        if not limit or not limit.isdigit():
            limit = "30"
            
        console.print("\n[yellow]Starting video screen record...[/yellow]")
        console.print("[bold red]Please interact with your watch now.[/bold red]")
        console.print(f"Record session will automatically terminate in {limit} seconds.")
        console.print("Press [bold cyan]ENTER[/bold cyan] in this console to terminate recording early...\n")
        
        # Start screenrecord process in background
        proc = subprocess.Popen([
            'adb', '-s', selected_device, 'shell', 'screenrecord', 
            '--time-limit', limit, '--size', '360x360', '/sdcard/temp_record.mp4'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # We wait for user keypress to stop or process to finish
        import select
        
        try:
            # Wait for either process to terminate or stdin input
            # select.select monitors file descriptors
            finished = False
            while not finished:
                # If process has finished on its own
                if proc.poll() is not None:
                    finished = True
                    break
                    
                # Non-blocking check for Enter key on stdin
                # Wait up to 0.5s
                r, w, x = select.select([sys.stdin], [], [], 0.5)
                if r:
                    sys.stdin.readline() # Consume input line
                    console.print("[yellow]Stopping recording early...[/yellow]")
                    # Find PID of screenrecord on the watch and send SIGINT (2)
                    rc_pid, stdout_pid, _ = run_adb(['shell', 'pidof', 'screenrecord'], selected_device)
                    if rc_pid == 0 and stdout_pid.strip():
                        run_adb(['shell', 'kill', '-2', stdout_pid.strip()], selected_device)
                    finished = True
                    break
        except Exception:
            # Fallback if select is interrupted
            proc.terminate()
            
        proc.wait() # Make sure process fully exits
        
        # Pull file from device
        console.print("[yellow]Downloading video recording...[/yellow]")
        rc_pull, _, _ = run_adb(['pull', '/sdcard/temp_record.mp4', dest_file], selected_device)
        run_adb(['shell', 'rm', '/sdcard/temp_record.mp4'], selected_device)
        
        if rc_pull == 0:
            console.print(f"[green]Success: Screen recording saved to: {dest_file}[/green]")
        else:
            console.print("[red]Failed to pull video file.[/red]")
        questionary.press_any_key_to_continue().ask()

# 9. REBOOT MANAGER
def reboot_manager_menu():
    global selected_device
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    show_header("Reboot & Power Options")
    
    choice = questionary.select(
        "Select Reboot Destination:",
        choices=[
            "Standard Reboot (Soft Restart)",
            "Reboot to Recovery Mode (For formatting / cache wipe)",
            "Reboot to Bootloader / Fastboot (For flashing firmware)",
            "Go Back"
        ]
    ).ask()
    
    if not choice or choice == "Go Back":
        return
        
    if "Standard Reboot" in choice:
        console.print("[yellow]Sending standard reboot command...[/yellow]")
        run_adb(['reboot'], selected_device)
        selected_device = None
        console.print("[green]Reboot signal sent. Device connection closed.[/green]")
        
    elif "Reboot to Recovery" in choice:
        console.print("[yellow]Rebooting watch to Recovery Mode...[/yellow]")
        run_adb(['reboot', 'recovery'], selected_device)
        selected_device = None
        console.print("[green]Rebooting to Recovery... Device connection closed.[/green]")
        
    elif "Reboot to Bootloader" in choice:
        console.print("[yellow]Rebooting watch to Bootloader Mode...[/yellow]")
        run_adb(['reboot', 'bootloader'], selected_device)
        selected_device = None
        console.print("[green]Rebooting to Bootloader... Device connection closed.[/green]")
        
    questionary.press_any_key_to_continue().ask()

def clear_caches_menu():
    show_header("Cache & Data Reset Utility")
    
    choices = [
        "1. Clear UAD Package Database Cache (Force refresh next time)",
        "2. Clear Local Connection & Debloat History files",
        "3. Clear All Watch App Caches (System-wide Cache Trim - safe, keeps logins)",
        "4. Reset Specific On-Device App Data (pm clear - wipes logins/settings)",
        "5. Go Back"
    ]
    
    choice = questionary.select("Select reset operation:", choices=choices).ask()
    if not choice or "Go Back" in choice:
        return
        
    if "Clear UAD Package Database Cache" in choice:
        if os.path.exists(UAD_CACHE_FILE):
            try:
                os.remove(UAD_CACHE_FILE)
                console.print("[green]Success: UAD cache deleted![/green]")
            except Exception as e:
                console.print(f"[red]Error deleting UAD cache: {e}[/red]")
        else:
            console.print("[yellow]UAD cache file does not exist.[/yellow]")
        questionary.press_any_key_to_continue().ask()
        
    elif "Clear Local Connection" in choice:
        deleted = []
        for file in [HISTORY_FILE, CONN_HISTORY_FILE]:
            if os.path.exists(file):
                try:
                    os.remove(file)
                    deleted.append(file)
                except Exception as e:
                    console.print(f"[red]Error deleting {file}: {e}[/red]")
        global selected_device
        selected_device = None
        if deleted:
            console.print(f"[green]Success: Deleted history files ({', '.join(deleted)})[/green]")
        else:
            console.print("[yellow]No history files found to delete.[/yellow]")
        questionary.press_any_key_to_continue().ask()
        
    elif "Clear All Watch App Caches" in choice:
        if not selected_device:
            console.print("[red]Please connect to a device first.[/red]")
            questionary.press_any_key_to_continue().ask()
            return
            
        console.print("[yellow]Starting watch app cache cleanup...[/yellow]")
        
        with console.status("[yellow]Trimming watch app caches (safe, preserves logins)...[/yellow]"):
            # 1. Clear external storage app caches
            run_adb(['shell', 'rm', '-rf', '/sdcard/Android/data/*/cache/*'], selected_device)
            # 2. Trigger system package manager cache trim (requests 999 GB free space)
            rc, stdout, stderr = run_adb(['shell', 'pm', 'trim-caches', '999999999999'], selected_device)
            
        if rc == 0:
            console.print("[green]Success: All watch application caches cleared system-wide![/green]")
            console.print("[cyan]This cleared cached files only. All app settings, database tables, and logins were preserved.[/cyan]")
        else:
            console.print(f"[red]Cache trim encountered a warning: {stderr.strip() or stdout.strip()}[/red]")
            console.print("[yellow]Common cache cleanup command executed. Some caches may require root to wipe manually.[/yellow]")
            
        questionary.press_any_key_to_continue().ask()
        
    elif "Reset Specific On-Device App Data" in choice:
        if not selected_device:
            console.print("[red]Please connect to a device first.[/red]")
            questionary.press_any_key_to_continue().ask()
            return
            
        console.print("[yellow]Fetching package list from watch...[/yellow]")
        pkg_status = get_device_packages(selected_device)
        if not pkg_status:
            console.print("[red]Failed to read packages.[/red]")
            questionary.press_any_key_to_continue().ask()
            return
            
        all_pkgs = sorted(pkg_status['active'])
        uad_data = load_uad_list()
        
        choices_pkgs = []
        for pkg in all_pkgs:
            friendly = get_friendly_name(pkg, uad_data)
            choices_pkgs.append(questionary.Choice(title=f"{friendly} ({pkg})", value=pkg))
            
        selected_pkgs = questionary.checkbox(
            "Select packages to reset (WARNING: this clears all database, settings, and cache files for these apps):",
            choices=choices_pkgs
        ).ask()
        
        if not selected_pkgs:
            return
            
        if not questionary.confirm("Are you absolutely sure you want to reset data/cache for these applications?").ask():
            return
            
        console.print("\n[bold yellow]Executing pm clear batch...[/bold yellow]\n")
        success_count = 0
        fail_count = 0
        
        for pkg in selected_pkgs:
            friendly = get_friendly_name(pkg, uad_data)
            console.print(f"Resetting: [cyan]{friendly}[/cyan] ({pkg})... ", end="")
            rc, stdout, stderr = run_adb(['shell', 'pm', 'clear', pkg], selected_device)
            if rc == 0 and "success" in stdout.lower():
                console.print("[green]SUCCESS[/green]")
                success_count += 1
            else:
                console.print(f"[red]FAILED[/red] ({stderr.strip() or stdout.strip()})")
                fail_count += 1
                
        console.print(f"\n[green]Completed! Success: {success_count}, Failed: {fail_count}[/green]")
        questionary.press_any_key_to_continue().ask()

def watch_optimizer_menu():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return

    show_header("Curated Watch Optimizer")
    console.print("[yellow]Select the optimizations you want to apply to your watch:[/yellow]\n")
    
    options = [
        questionary.Choice(
            title="Snappier Animations (Set window/transition/animator scale to 0.5x)",
            value="animations",
            checked=True
        ),
        questionary.Choice(
            title="Faster Touch Response (Reduce long press & multi-press timeouts to 250ms)",
            value="touch_response",
            checked=True
        ),
        questionary.Choice(
            title="Disable Virtual RAM (RAM Plus = 0) - reduces storage wear & stuttering",
            value="ram_plus",
            checked=True
        ),
        questionary.Choice(
            title="Disable Background Wi-Fi Location Scanning - saves massive battery",
            value="wifi_scan",
            checked=True
        ),
        questionary.Choice(
            title="Disable Background BLE Location Scanning - saves massive battery",
            value="ble_scan",
            checked=True
        ),
        questionary.Choice(
            title="Throttle Background Location Updates (Set interval to 30 mins) - saves battery",
            value="location_throttle",
            checked=True
        ),
        questionary.Choice(
            title="System-Wide Ad-Blocking (Enable AdGuard Private DNS on watch)",
            value="adguard_dns",
            checked=True
        ),
        questionary.Choice(
            title="Disable Accessibility Live Captions - saves background CPU cycles",
            value="captions",
            checked=True
        ),
        questionary.Choice(
            title="Enable Predictive Back Animations (Supported on WearOS 5/6)",
            value="predictive_back",
            checked=False
        ),
        questionary.Choice(
            title="Max Flashlight Brightness Level (Set flashlight default to maximum)",
            value="flashlight",
            checked=False
        ),
        questionary.Choice(
            title="Optimize App Launch Speeds (Run profile-guided AOT compiler) - takes ~1 min",
            value="compile_speed",
            checked=False
        ),
        questionary.Choice(
            title="Force Enable Battery Saver Mode (Low Power Mode)",
            value="low_power",
            checked=False
        ),
        questionary.Choice(
            title="Disable Watch GPS / Location Services entirely - saves battery",
            value="location_mode",
            checked=False
        ),
        questionary.Choice(
            title="Disable Watch Wi-Fi Radio entirely (Force Bluetooth only) - saves battery",
            value="wifi_on",
            checked=False
        ),
        questionary.Choice(
            title="Disable Tilt-to-Wake (Wrist gesture to turn screen on) - saves massive battery",
            value="tilt_to_wake",
            checked=False
        ),
        questionary.Choice(
            title="Disable Touch-to-Wake (Tapping screen to wake up watch) - saves battery",
            value="touch_to_wake",
            checked=False
        ),
        questionary.Choice(
            title="Disable Always-on Display (AOD / Ambient Mode) - saves massive battery",
            value="ambient_display",
            checked=False
        ),
        questionary.Choice(
            title="Disable System Diagnostics & Background Logging - saves CPU/battery",
            value="logging",
            checked=False
        )
    ]
    
    selected = questionary.checkbox(
        "Select optimizations (Space to select/deselect, Enter to confirm):",
        choices=options
    ).ask()
    
    if not selected:
        return
        
    console.print("\n[bold yellow]Applying watch optimizations...[/bold yellow]\n")
    success_count = 0
    fail_count = 0
    
    def apply_tweak(desc, cmd_args):
        nonlocal success_count, fail_count
        console.print(f"Applying: [cyan]{desc}[/cyan]... ", end="")
        rc, stdout, stderr = run_adb(cmd_args, selected_device)
        if rc == 0:
            console.print("[green]OK[/green]")
            success_count += 1
        else:
            console.print(f"[red]FAILED[/red] ({stderr.strip() or stdout.strip()})")
            fail_count += 1
            
    if "animations" in selected:
        apply_tweak("Window animation scale (0.5x)", ['shell', 'settings', 'put', 'global', 'window_animation_scale', '0.5'])
        apply_tweak("Transition animation scale (0.5x)", ['shell', 'settings', 'put', 'global', 'transition_animation_scale', '0.5'])
        apply_tweak("Animator duration scale (0.5x)", ['shell', 'settings', 'put', 'global', 'animator_duration_scale', '0.5'])
        
    if "touch_response" in selected:
        apply_tweak("Long press timeout (250ms)", ['shell', 'settings', 'put', 'secure', 'long_press_timeout', '250'])
        apply_tweak("Multi-press timeout (250ms)", ['shell', 'settings', 'put', 'secure', 'multi_press_timeout', '250'])
        
    if "ram_plus" in selected:
        apply_tweak("Disable Virtual RAM (RAM Plus = 0)", ['shell', 'settings', 'put', 'global', 'ram_expand_size', '0'])
        
    if "wifi_scan" in selected:
        apply_tweak("Disable Location Wi-Fi scanning", ['shell', 'settings', 'put', 'global', 'wifi_scan_always', '0'])
        
    if "ble_scan" in selected:
        apply_tweak("Disable Location BLE scanning", ['shell', 'settings', 'put', 'global', 'ble_scan_always', '0'])
        
    if "location_throttle" in selected:
        apply_tweak("Throttle background location checks", ['shell', 'settings', 'put', 'secure', 'location_background_throttle_interval_ms', '1800000'])
        
    if "adguard_dns" in selected:
        apply_tweak("Enable AdGuard Private DNS specifier", ['shell', 'settings', 'put', 'global', 'private_dns_specifier', 'dns.adguard-dns.com'])
        apply_tweak("Set Private DNS mode to hostname", ['shell', 'settings', 'put', 'global', 'private_dns_mode', 'hostname'])
        
    if "captions" in selected:
        apply_tweak("Disable Accessibility Captions", ['shell', 'settings', 'put', 'secure', 'accessibility_captioning_enabled', '0'])
        apply_tweak("Disable Live Captions (ODI)", ['shell', 'settings', 'put', 'secure', 'odi_captions_enabled', '0'])
        
    if "predictive_back" in selected:
        apply_tweak("Enable Predictive Back Animations", ['shell', 'settings', 'put', 'global', 'enable_back_animation', '1'])
        
    if "flashlight" in selected:
        apply_tweak("Set Flashlight brightness to maximum", ['shell', 'settings', 'put', 'system', 'Flashlight_brightness_level', '1001'])

    if "compile_speed" in selected:
        console.print("[yellow]Running profile-guided AOT compilation for all apps. Streaming output...[/yellow]")
        rc = run_adb_stream(['shell', 'cmd', 'package', 'compile', '-m', 'speed-profile', '-a'], selected_device, timeout=300)
        if rc == 0:
            console.print("[green]AOT compilation completed successfully![/green]")
            success_count += 1
        else:
            console.print("[red]AOT compilation failed or timed out.[/red]")
            fail_count += 1

    if "low_power" in selected:
        apply_tweak("Force Enable Battery Saver Mode", ['shell', 'settings', 'put', 'global', 'low_power', '1'])

    if "location_mode" in selected:
        apply_tweak("Disable GPS / Location Services entirely", ['shell', 'settings', 'put', 'secure', 'location_mode', '0'])

    if "wifi_on" in selected:
        apply_tweak("Disable Wi-Fi Radio entirely", ['shell', 'settings', 'put', 'global', 'wifi_on', '0'])

    if "tilt_to_wake" in selected:
        apply_tweak("Disable Tilt-to-Wake wrist gesture", ['shell', 'settings', 'put', 'secure', 'ambient_tilt_to_wake', '0'])

    if "touch_to_wake" in selected:
        apply_tweak("Disable Touch-to-Wake screen gesture", ['shell', 'settings', 'put', 'secure', 'touchscreen_wake', '0'])

    if "ambient_display" in selected:
        apply_tweak("Disable Always-on Display (AOD secure setting)", ['shell', 'settings', 'put', 'secure', 'ambient_enabled', '0'])
        apply_tweak("Disable Always-on Display (AOD global setting)", ['shell', 'settings', 'put', 'global', 'ambient_enabled', '0'])

    if "logging" in selected:
        apply_tweak("Disable System Error Diagnostic reporting", ['shell', 'settings', 'put', 'secure', 'send_action_app_error', '0'])
        apply_tweak("Disable Activity Starts logging", ['shell', 'settings', 'put', 'global', 'activity_starts_logging_enabled', '0'])
        
    console.print(f"\n[green]Optimizations finished! Successfully applied: {success_count}, Failed: {fail_count}[/green]")
    
    if questionary.confirm("\nWould you like to customize your Watch's name (Bluetooth/Device Name)?").ask():
        watch_name = questionary.text("Enter new Watch Name (e.g. My Galaxy Watch):").ask()
        if watch_name and watch_name.strip():
            name = watch_name.strip()
            # adb forwards args to the watch's /system/bin/sh, which re-parses
            # them. Quote the name so spaces and apostrophes (e.g. "Dmytrii's
            # Galaxy Watch") survive intact instead of breaking the command.
            qname = shlex.quote(name)
            ok_before = success_count
            apply_tweak("Set Bluetooth device name", ['shell', 'settings', 'put', 'secure', 'bluetooth_name', qname])
            apply_tweak("Set synced account device name", ['shell', 'settings', 'put', 'global', 'synced_account_name', qname])
            apply_tweak("Set global device name", ['shell', 'settings', 'put', 'global', 'device_name', qname])
            apply_tweak("Set default device name", ['shell', 'settings', 'put', 'global', 'default_device_name', qname])
            if success_count > ok_before:
                console.print(f"[green]Watch name updated to \"{name}\" ({success_count - ok_before}/4 settings applied). A reboot may be needed to refresh it on paired devices.[/green]")
            else:
                console.print("[red]Watch name could not be updated (none of the settings keys were writable on this device).[/red]")
            
    questionary.press_any_key_to_continue().ask()

# --- Debloater Engine Wrappers (Already Implemented) ---
def quick_debloat_menu():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    show_header("Quick Debloat Catalog")
    
    categories = list(CATALOG.keys())
    categories.append("Cancel")
    
    category = questionary.select(
        "Choose Watch Brand Catalog to Debloat:",
        choices=categories
    ).ask()
    
    if not category or category == "Cancel":
        return
        
    catalog_apps = CATALOG[category]
    
    console.print("[yellow]Checking device package status...[/yellow]")
    pkg_status = get_device_packages(selected_device)
    if not pkg_status:
        console.print("[red]Failed to read packages from device. Connection might have been lost.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    choices = []
    for app in catalog_apps:
        pkg = app['package']
        
        if pkg in pkg_status['active']:
            status_str = "[Active]"
            is_checked = (app['safety'] == 'Safe')
        elif pkg in pkg_status['disabled']:
            status_str = "[Disabled]"
            is_checked = False
        else:
            continue  # Package not on watch
            
        safety_color = "green" if app['safety'] == "Safe" else "yellow"
        display_title = f"{app['name']} ({pkg}) - {status_str} [Safety: {app['safety']}]"
        
        choices.append(
            questionary.Choice(
                title=display_title,
                value=app,
                checked=is_checked
            )
        )
            
    if not choices:
        console.print("[green]No catalog bloatware apps found active on your watch![/green]")
        questionary.press_any_key_to_continue().ask()
        return
        
    selected_apps = questionary.checkbox(
        "Select the apps you want to debloat (Space to select, Enter to confirm):",
        choices=choices
    ).ask()
    
    if not selected_apps:
        return
        
    action_type = questionary.select(
        "What action would you like to take?",
        choices=[
            "Disable (Recommended)",
            "Uninstall for User 0 (Thorough)",
            "Cancel"
        ]
    ).ask()
    
    if not action_type or action_type == "Cancel":
        return
        
    is_uninstall = "Uninstall" in action_type
    action_name = "uninstall" if is_uninstall else "disable"
    
    console.print(f"\n[bold yellow]Executing batch {action_name}...[/bold yellow]\n")
    success_count = 0
    fail_count = 0
    
    for app in selected_apps:
        pkg = app['package']
        console.print(f"Processing: [cyan]{app['name']}[/cyan] ({pkg})... ", end="")
        
        if is_uninstall:
            success, msg = execute_uninstall(selected_device, pkg)
        else:
            success, msg = execute_disable(selected_device, pkg)
            
        if success:
            console.print("[green]SUCCESS[/green]")
            success_count += 1
        else:
            console.print(f"[red]FAILED[/red] ({msg})")
            fail_count += 1
            
    console.print(f"\n[green]Completed! Success: {success_count}, Failed: {fail_count}[/green]")
    questionary.press_any_key_to_continue().ask()

def uad_auto_debloat_menu():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return

    show_header("UAD-NG Auto-Debloater")
    
    # Load list
    uad_data = load_uad_list()
    if not uad_data:
        console.print("[yellow]UAD-NG package database is empty or not cached.[/yellow]")
        if questionary.confirm("Would you like to download the latest database from GitHub?").ask():
            uad_data = update_uad_list()
        else:
            return
            
    if not uad_data:
        console.print("[red]Failed to load UAD database. Action aborted.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    console.print("[yellow]Fetching package list from watch...[/yellow]")
    pkg_status = get_device_packages(selected_device)
    if not pkg_status:
        console.print("[red]Failed to read packages from watch.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    # Query brand prop
    _, brand, _ = run_adb(['shell', 'getprop', 'ro.product.brand'], selected_device)
    brand = brand.strip().lower()
    
    # Define brand lists to match
    allowed_lists = ["aosp", "google", "oem", "carrier"]
    if "samsung" in brand:
        allowed_lists.append("samsung")
    elif "xiaomi" in brand:
        allowed_lists.append("xiaomi")
    elif "mobvoi" in brand or "ticwatch" in brand:
        allowed_lists.append("mobvoi")
    elif "motorola" in brand:
        allowed_lists.append("motorola")
        
    recommended_debloat = []
    other_debloat = []
    
    present_packages = pkg_status['active'] + pkg_status['disabled']
    
    for pkg in present_packages:
        if pkg in uad_data:
            info = uad_data[pkg]
            pkg_list = info.get("list", "Unknown").lower()
            removal = info.get("removal", "Recommended")
            
            # Skip lists that belong to other known brands
            known_brands = ["samsung", "xiaomi", "huawei", "motorola", "oneplus", "oppo", "sony", "asus", "lg"]
            if pkg_list in known_brands and pkg_list not in allowed_lists:
                continue
                
            is_disabled = pkg in pkg_status['disabled']
            friendly = get_friendly_name(pkg, uad_data)
            choice_item = make_pkg_choice(
                pkg, friendly, removal, is_disabled,
                value={"package": pkg, "info": info},
                checked=(removal == "Recommended" and not is_disabled),
                description=info.get("description"),
            )

            if removal == "Recommended":
                recommended_debloat.append(choice_item)
            elif removal in ["Advanced", "Expert"]:
                other_debloat.append(choice_item)

    choices = recommended_debloat + other_debloat

    if not choices:
        console.print("[green]No UAD-matched bloatware packages found on your watch![/green]")
        if questionary.confirm("Would you like to manually download/update the UAD database?").ask():
            update_uad_list()
        return

    console.print(f"[cyan]{len(choices)} UAD matches[/cyan] ([green]{len(recommended_debloat)} recommended[/green], [yellow]{len(other_debloat)} advanced/expert[/yellow]).  {REC_LEGEND}")

    selected = checkbox_with_info(
        "Select packages to debloat (recommended pre-selected):",
        choices=choices,
        instruction="(space=select · →=info · a=all · i=invert · enter=confirm)",
    ).ask()
    
    if not selected:
        return
        
    # Detail display & Confirmation
    show_header("Confirm UAD Auto-Debloat")
    table = Table(title="Apps Selected for Debloating")
    table.add_column("Package Name", style="cyan")
    table.add_column("UAD Category", style="green")
    table.add_column("Recommendation", style="yellow")
    table.add_column("Description", style="white")
    
    for item in selected:
        pkg = item['package']
        info = item['info']
        desc = info.get("description", "No description available.").replace('\n', ' ')
        if len(desc) > 80:
            desc = desc[:77] + "..."
        table.add_row(
            pkg,
            info.get("list", "N/A"),
            info.get("removal", "N/A"),
            desc
        )
    console.print(table)
    
    action_type = questionary.select(
        "\nWhat action would you like to take on these apps?",
        choices=[
            "Disable (Recommended - safe and reversible)",
            "Uninstall for User 0 (Thorough)",
            "Cancel"
        ]
    ).ask()
    
    if not action_type or action_type == "Cancel":
        return
        
    is_uninstall = "Uninstall" in action_type
    action_name = "uninstall" if is_uninstall else "disable"
    
    console.print(f"\n[bold yellow]Executing UAD batch {action_name}...[/bold yellow]\n")
    success_count = 0
    fail_count = 0
    
    for item in selected:
        pkg = item['package']
        console.print(f"Processing: [cyan]{pkg}[/cyan]... ", end="")
        if is_uninstall:
            success, msg = execute_uninstall(selected_device, pkg)
        else:
            success, msg = execute_disable(selected_device, pkg)
            
        if success:
            console.print("[green]SUCCESS[/green]")
            success_count += 1
        else:
            console.print(f"[red]FAILED[/red] ({msg})")
            fail_count += 1
            
    console.print(f"\n[green]Completed UAD Auto-Debloat! Success: {success_count}, Failed: {fail_count}[/green]")
    questionary.press_any_key_to_continue().ask()

def custom_debloat_menu():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    show_header("Custom Debloat Utility")
    
    filter_keyword = questionary.text(
        "Filter by name or package id (blank = show all):"
    ).ask()
    
    if filter_keyword is None:
        return
        
    filter_keyword = filter_keyword.strip().lower()
    
    console.print("[yellow]Fetching package list from watch...[/yellow]")
    pkg_status = get_device_packages(selected_device)
    if not pkg_status:
        console.print("[red]Failed to read packages from device.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    # Load UAD data for custom selection context
    uad_data = load_uad_list()
    
    all_packages = pkg_status['active'] + pkg_status['disabled']

    entries = []
    for pkg in all_packages:
        friendly = get_friendly_name(pkg, uad_data)
        if filter_keyword and filter_keyword not in pkg.lower() and filter_keyword not in friendly.lower():
            continue

        is_disabled = pkg in pkg_status['disabled']

        catalog_match = None
        for cat, apps in CATALOG.items():
            for app in apps:
                if app['package'] == pkg:
                    catalog_match = app
                    break
            if catalog_match:
                break

        uad_match = uad_data.get(pkg)
        if catalog_match:
            rating = catalog_match['safety']
            desc = catalog_match.get('desc')
        elif uad_match:
            rating = uad_match.get('removal')
            desc = uad_match.get('description')
        else:
            rating = None
            desc = None

        entries.append((pkg, friendly, rating, is_disabled, desc))

    if not entries:
        console.print("[yellow]No matching packages found on the device.[/yellow]")
        questionary.press_any_key_to_continue().ask()
        return

    # Surface the safest/most actionable packages at the top of the list.
    entries.sort(key=lambda e: (rec_badge(e[2])[1], e[0]))
    choices = [
        make_pkg_choice(p, f, r, d, description=desc)
        for (p, f, r, d, desc) in entries
    ]

    console.print(f"[cyan]{len(choices)} matching packages.[/cyan]  {REC_LEGEND}")
    selected_pkgs = checkbox_with_info(
        "Select packages to debloat:",
        choices=choices,
        instruction="(space=select · →=info · a=all · i=invert · enter=confirm)",
    ).ask()
    
    if not selected_pkgs:
        return
        
    # Show detail table
    show_header("Confirm Custom Debloat Selection")
    table = Table(title="Apps Selected for Debloating")
    table.add_column("App Name (Package)", style="cyan")
    table.add_column("Source", style="green")
    table.add_column("Recommendation / Safety", style="yellow")
    table.add_column("Description", style="white")

    for pkg in selected_pkgs:
        friendly = get_friendly_name(pkg, uad_data)
        cat_match = None
        for cat, apps in CATALOG.items():
            for app in apps:
                if app['package'] == pkg:
                    cat_match = app
                    break
            if cat_match:
                break
        
        uad_match = uad_data.get(pkg)
        
        if cat_match:
            desc = cat_match.get("desc", "N/A").replace('\n', ' ')
            src = "Built-in Catalog"
            rec = cat_match.get("safety", "N/A")
        elif uad_match:
            desc = uad_match.get("description", "N/A").replace('\n', ' ')
            src = f"UAD ({uad_match.get('list', 'N/A')})"
            rec = uad_match.get("removal", "N/A")
        else:
            desc = "No package description database entry."
            src = "System Package"
            rec = "N/A"
            
        if len(desc) > 80:
            desc = desc[:77] + "..."
            
        table.add_row(f"{friendly} ({pkg})", src, rec, desc)
        
    console.print(table)
        
    action_type = questionary.select(
        "\nWhat action would you like to take on the selected packages?",
        choices=[
            "Disable (Recommended)",
            "Uninstall for User 0",
            "Cancel"
        ]
    ).ask()
    
    if not action_type or action_type == "Cancel":
        return
        
    is_uninstall = "Uninstall" in action_type
    action_name = "uninstall" if is_uninstall else "disable"
    
    console.print(f"\n[bold yellow]Executing custom {action_name} batch...[/bold yellow]\n")
    success_count = 0
    fail_count = 0
    
    for pkg in selected_pkgs:
        console.print(f"Processing: [cyan]{pkg}[/cyan]... ", end="")
        if is_uninstall:
            success, msg = execute_uninstall(selected_device, pkg)
        else:
            success, msg = execute_disable(selected_device, pkg)
            
        if success:
            console.print("[green]SUCCESS[/green]")
            success_count += 1
        else:
            console.print(f"[red]FAILED[/red] ({msg})")
            fail_count += 1
            
    console.print(f"\n[green]Completed! Success: {success_count}, Failed: {fail_count}[/green]")
    questionary.press_any_key_to_continue().ask()

def restore_menu():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    show_header("Restore / Re-enable Packages")
    
    sub_choice = questionary.select(
        "Choose how you want to restore packages:",
        choices=[
            "Restore from Local Debloat History",
            "Restore from all Disabled packages on the Watch",
            "Restore from all Uninstalled (User 0) packages on the Watch",
            "Manual restore (Enter package name)",
            "Go Back"
        ]
    ).ask()
    
    if not sub_choice or sub_choice == "Go Back":
        return
        
    pkg_status = None
    if sub_choice != "Manual restore (Enter package name)":
        console.print("[yellow]Querying watch package state...[/yellow]")
        pkg_status = get_device_packages(selected_device)
        if not pkg_status:
            console.print("[red]Failed to communicate with watch.[/red]")
            questionary.press_any_key_to_continue().ask()
            return
    # Load UAD data for friendly names in restore menu
    uad_data = load_uad_list()
    choices = []
    
    if sub_choice == "Restore from Local Debloat History":
        history = load_json(HISTORY_FILE)
        device_hist = history.get(selected_device, {})
        if not device_hist:
            console.print("[yellow]No local debloat history found for this device.[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
            
        for pkg, data in device_hist.items():
            action = data.get("action", "unknown")
            timestamp = data.get("timestamp", "unknown time")
            friendly = get_friendly_name(pkg, uad_data)
            choices.append(
                questionary.Choice(
                    title=f"{friendly} ({pkg}) [History: {action} on {timestamp}]",
                    value={"package": pkg, "action": action}
                )
            )
            
    elif sub_choice == "Restore from all Disabled packages on the Watch":
        disabled = pkg_status['disabled']
        if not disabled:
            console.print("[green]No disabled packages detected on the watch.[/green]")
            questionary.press_any_key_to_continue().ask()
            return
        for pkg in disabled:
            friendly = get_friendly_name(pkg, uad_data)
            choices.append(questionary.Choice(title=f"{friendly} ({pkg})", value={"package": pkg, "action": "disabled"}))
            
    elif sub_choice == "Restore from all Uninstalled (User 0) packages on the Watch":
        uninstalled = pkg_status['uninstalled']
        if not uninstalled:
            console.print("[green]No uninstalled (User 0) packages detected on the watch.[/green]")
            questionary.press_any_key_to_continue().ask()
            return
        for pkg in uninstalled:
            friendly = get_friendly_name(pkg, uad_data)
            choices.append(questionary.Choice(title=f"{friendly} ({pkg})", value={"package": pkg, "action": "uninstalled"}))
            
    elif sub_choice == "Manual restore (Enter package name)":
        manual_pkg = questionary.text("Enter full package name to restore (e.g. com.samsung.android.bixby.agent):").ask()
        if not manual_pkg or not manual_pkg.strip():
            return
        action = questionary.select(
            "How was it debloated?",
            choices=["Disabled (Restore via Enable)", "Uninstalled (Restore via Install-Existing)"]
        ).ask()
        if not action:
            return
        is_uninstall = "Uninstalled" in action
        friendly = get_friendly_name(manual_pkg.strip(), uad_data)
        choices = [
            questionary.Choice(
                title=f"{friendly} ({manual_pkg.strip()})", 
                value={"package": manual_pkg.strip(), "action": "uninstalled" if is_uninstall else "disabled"},
                checked=True
            )
        ]
        
    selected_restores = questionary.checkbox(
        "Select packages to restore (Space to select, Enter to confirm):",
        choices=choices
    ).ask()
    
    if not selected_restores:
        return
        
    console.print("\n[bold yellow]Executing restore batch...[/bold yellow]\n")
    success_count = 0
    fail_count = 0
    
    for item in selected_restores:
        pkg = item['package']
        action = item['action']
        friendly = get_friendly_name(pkg, uad_data)
        console.print(f"Restoring: [cyan]{friendly}[/cyan] ({pkg}) [{action}]... ", end="")
        
        if action == "uninstalled":
            success, msg = execute_reinstall(selected_device, pkg)
        else:
            success, msg = execute_enable(selected_device, pkg)
            
        if success:
            console.print("[green]SUCCESS[/green]")
            success_count += 1
        else:
            console.print(f"[red]FAILED[/red] ({msg})")
            fail_count += 1
            
    console.print(f"\n[green]Completed Restore! Success: {success_count}, Failed: {fail_count}[/green]")
    questionary.press_any_key_to_continue().ask()

def execute_disable(device_serial, package):
    rc, stdout, stderr = run_adb(['shell', 'pm', 'disable-user', '--user', '0', package], device_serial)
    if rc == 0 and "disabled" in stdout.lower():
        log_action_to_history(device_serial, package, "disabled")
        return True, stdout.strip()
    return False, stderr.strip() or stdout.strip()

def execute_uninstall(device_serial, package):
    rc, stdout, stderr = run_adb(['shell', 'pm', 'uninstall', '-k', '--user', '0', package], device_serial)
    if rc == 0 and "success" in stdout.lower():
        log_action_to_history(device_serial, package, "uninstalled")
        return True, stdout.strip()
    return False, stderr.strip() or stdout.strip()

def execute_enable(device_serial, package):
    rc, stdout, stderr = run_adb(['shell', 'pm', 'enable', package], device_serial)
    if rc == 0 and "enabled" in stdout.lower():
        history = load_json(HISTORY_FILE)
        if device_serial in history and package in history[device_serial]:
            history[device_serial].pop(package)
            save_json(HISTORY_FILE, history)
        return True, stdout.strip()
    return False, stderr.strip() or stdout.strip()

def execute_reinstall(device_serial, package):
    rc, stdout, stderr = run_adb(['shell', 'cmd', 'package', 'install-existing', package], device_serial)
    if rc == 0 and "installed" in stdout.lower():
        history = load_json(HISTORY_FILE)
        if device_serial in history and package in history[device_serial]:
            history[device_serial].pop(package)
            save_json(HISTORY_FILE, history)
        return True, stdout.strip()
    return False, stderr.strip() or stdout.strip()

def run_shell_command():
    if not selected_device:
        console.print("[red]Please connect to a device first.[/red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    show_header("Interactive ADB Shell Console")
    console.print("[yellow]Type custom watch commands (e.g. 'pm list features', 'logcat -d').[/yellow]")
    console.print("Type 'exit' to return to Main Menu.\n")
    
    while True:
        cmd = console.input("[bold green]adb shell @ watch > [/bold green]").strip()
        if not cmd or cmd.lower() == 'exit':
            break

        # shlex preserves quoted arguments (e.g. paths with spaces) instead of
        # naively splitting on every space.
        try:
            cmd_parts = shlex.split(cmd)
        except ValueError as e:
            console.print(f"[red]Invalid command syntax: {e}[/red]")
            continue
        args = ['shell'] + cmd_parts
        rc, stdout, stderr = run_adb(args, selected_device)
        
        if rc == 0:
            console.print(stdout)
        else:
            if stderr:
                console.print(f"[red]{stderr}[/red]")
            else:
                console.print(stdout)

# --- Main Routing Loop ---
def main_loop():
    # (label, handler) — display is decoupled from routing via Choice values.
    menu = [
        ("Connect / Pair",          select_device_menu),
        ("Diagnostics",             show_device_dashboard),
        ("Apps: Sideload & Backup", apk_manager_menu),
        ("Quick Debloat",           quick_debloat_menu),
        ("UAD-NG Auto-Debloat",     uad_auto_debloat_menu),
        ("Custom Debloat",          custom_debloat_menu),
        ("Restore / Re-enable",     restore_menu),
        ("File Transfer",           file_explorer_menu),
        ("Input & Control",         interact_tools_menu),
        ("Display & Screen",        display_settings_menu),
        ("Audio & Sound",           audio_manager_menu),
        ("Screen Capture",          screen_capture_menu),
        ("Reboot",                  reboot_manager_menu),
        ("Clear Caches & Reset",    clear_caches_menu),
        ("Watch Optimizer",         watch_optimizer_menu),
        ("ADB Shell",               run_shell_command),
    ]

    while True:
        show_header("Main Menu")

        choices = [
            questionary.Choice(title=f"{i}. {label}", value=label)
            for i, (label, _) in enumerate(menu, start=1)
        ]
        choices.append(questionary.Choice(title="0. Exit", value="__exit__"))

        choice = questionary.select("Select:", choices=choices).ask()

        if not choice or choice == "__exit__":
            console.print("[cyan]Goodbye![/cyan]")
            break

        handler = dict(menu)[choice]
        try:
            handler()
        except KeyboardInterrupt:
            # Let Ctrl-C bubble up to the top-level handler to quit cleanly.
            raise
        except Exception as exc:
            # A failure in one menu must not take down the whole tool.
            logger.exception("Unhandled error in '%s'", choice)
            console.print(f"\n[bold red]Something went wrong in '{choice}':[/bold red] {exc}")
            console.print(f"[dim]Details were written to {LOG_FILE}[/dim]")
            questionary.press_any_key_to_continue().ask()

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="wearforge",
        description=f"{APP_NAME} — an all-in-one ADB toolkit for Wear OS: debloat, tweak, and manage your watch.",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"{APP_NAME} {APP_VERSION}",
    )
    parser.add_argument(
        "-d", "--device", metavar="SERIAL",
        help="Target a specific device serial or IP:PORT at startup.",
    )
    parser.add_argument(
        "--no-auto-connect", action="store_true",
        help="Do not auto-select the first connected device on startup.",
    )
    parser.add_argument(
        "--update-uad", action="store_true",
        help="Update the UAD-NG package database from GitHub and exit.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Also print debug logs to the console (always written to the log file).",
    )
    return parser.parse_args(argv)


def main():
    global selected_device
    args = parse_args()

    setup_logging(verbose=args.verbose)
    init_workspace()

    rc, _, _ = run_adb(['version'])
    if rc < 0:
        console.print("[bold red]Critical Error: adb executable not found on system PATH.[/bold red]")
        console.print("Please install Android SDK Platform Tools (adb) and run again.")
        sys.exit(1)

    # Non-interactive: refresh the UAD database and exit.
    if args.update_uad:
        update_uad_list()
        return

    devices = get_connected_devices()

    if args.device:
        match = next((d for d in devices if d['serial'] == args.device), None)
        if match is None:
            console.print(f"[yellow]Requested device '{args.device}' is not currently connected. Continuing without a target.[/yellow]")
        elif match['state'] != 'device':
            console.print(f"[red]Device '{args.device}' is in state '{match['state']}' (not ready). Continuing without a target.[/red]")
        else:
            selected_device = args.device
            log_connection_to_history(selected_device, get_device_info(selected_device))
    elif not args.no_auto_connect:
        # Auto target first connected device if one exists
        device_targets = [d for d in devices if d['state'] == 'device']
        if device_targets:
            selected_device = device_targets[0]['serial']
            log_connection_to_history(selected_device, get_device_info(selected_device))

    main_loop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[cyan]Exiting... Goodbye![/cyan]")
    except Exception as exc:
        logger.exception("Fatal error")
        console.print(f"\n[bold red]Fatal error:[/bold red] {exc}")
        console.print(f"[dim]See {LOG_FILE} for the full traceback.[/dim]")
        sys.exit(1)
