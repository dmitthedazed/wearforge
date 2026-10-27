# Contributing

## Setup

```sh
git clone https://github.com/dmitthedazed/wearforge.git
cd wearforge
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The whole app is one file, `wearforge.py`.

## Rules of thumb

- Talk to the watch only through `run_adb()` / `run_adb_stream()`.
- Wrap anything the user types with `shlex.quote()` before passing it to `adb shell`.
- Keep files in `DATA_DIR`, never in the current directory.
- New main menu item: write a `something_menu()` function and add it to `sections` in `main_loop`.
- Prefer `pm disable-user` over uninstall, and ask before anything destructive.
- Tests run without a device or network. If you change a helper, update `tests/`.

## Debloat catalog

Packages live in `CATALOG` at the top of `wearforge.py`:

```python
{
    "package": "com.example.bloat",
    "name": "Example App",
    "desc": "What it does and when it's safe to disable.",
    "safety": "Safe",  # or "Caution"
}
```

Only add packages you've seen on a real watch. If disabling one can break alarms, calls, SOS or similar, mark it `"Caution"`.

## Pull requests

Keep them small. In the description, mention which watch you tested on and which menus you touched.
