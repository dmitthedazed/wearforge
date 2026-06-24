# Contributing to WearForge

Thanks for your interest in improving WearForge! This is a single-file Python
TUI that drives [ADB](https://developer.android.com/tools/adb) to manage Wear OS
watches. Contributions of all sizes are welcome — bug reports, new catalog
entries, features, and docs.

## Getting set up

You need **Python 3.8+** and **`adb`** on your `PATH`.

```bash
git clone https://github.com/dmitthedazed/wearforge.git
cd wearforge
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the app:

```bash
wearforge            # installed entry point
# or, zero-install:
./run.sh
```

Run the tests:

```bash
pytest
```

## Project layout

| Path | What it is |
| --- | --- |
| `wearforge.py` | The whole application — one module. |
| `tests/` | `pytest` unit tests for the pure helpers. |
| `pyproject.toml` | Packaging, dependencies, entry point, pytest config. |
| `run.sh` | Bootstrap launcher (creates a venv, installs deps, runs the app). |
| `.github/workflows/ci.yml` | CI: byte-compile + tests on Python 3.8 / 3.10 / 3.12. |

The code is organized top-to-bottom as: constants/`CATALOG` → data-dir &
logging setup → helpers → ADB runners → feature menus → `main_loop` → `main`.

### How things fit together

- **Every device interaction goes through `run_adb(...)` / `run_adb_stream(...)`.**
  Don't call `subprocess` directly — the runner centralizes timeouts, logging,
  and the "adb not found" case.
- **The main menu is a dispatch table** in `main_loop`: a list of
  `(label, handler)` tuples. To add a top-level feature, write a
  `your_feature_menu()` function and add one entry — routing is automatic, and
  any exception it raises is caught so it can't crash the whole app.
- **Selection lists use `make_pkg_choice(...)` and `checkbox_with_info(...)`** so
  rows stay aligned and the → gesture can reveal descriptions. Reuse them rather
  than hand-building `questionary.Choice` rows.
- **State lives in the data dir**, not the working directory. Use the
  `DATA_DIR` / `BACKUPS_DIR` / `HISTORY_FILE` constants — never hard-code a
  relative path like `"backups/..."`.
- **Quote anything user-supplied** that becomes part of an `adb shell` command
  with `shlex.quote()` (the watch's shell re-parses the args).

## Adding a debloat catalog entry

The curated catalog is the `CATALOG` dict near the top of `wearforge.py`. Each
entry looks like:

```python
{
    "package": "com.example.bloat",
    "name": "Human-Friendly Name",
    "desc": "What it does and when it's safe to remove.",
    "safety": "Safe",   # "Safe" | "Caution"
}
```

Guidelines:
- Only add packages you've verified exist on a real device.
- Mark anything that can break core functionality (alarms, contacts, safety/SOS,
  TTS) as `"Caution"` and say so in `desc`.
- Prefer entries that the disable (not uninstall) path can reverse.

## Tests

- Tests must stay **hermetic** — no real device, no network. We only unit-test
  the pure helpers (name formatting, badges, path resolution, arg parsing, JSON).
- If you add or change a pure helper, add/adjust a test in
  `tests/test_wearforge.py`.
- Device-touching code is validated manually (see below) since CI has no watch.

## Manual testing with a watch

Most features can't be unit-tested, so describe your manual verification in the
PR. A quick loop:

1. Enable **Wireless Debugging** on the watch and connect (`wearforge` → Connect
   / Pair, or `adb connect IP:PORT`).
2. Exercise the menu you changed.
3. Run with `--verbose` and check `~/.local/share/wearforge/wearforge.log` if
   something fails.

Testing against the Android emulator (a Wear OS AVD) is fine for most package
and `settings` operations.

## Submitting changes

1. Branch off `main`: `git checkout -b my-change`.
2. Keep changes focused; match the surrounding style (4-space indent, snake_case,
   Rich markup for output).
3. Make sure `pytest` passes and `python -m compileall wearforge.py` is clean.
4. Open a PR describing **what** changed, **why**, and **how you tested it**
   (which watch/emulator, which menus).

### Commit messages

Use a short imperative summary line (e.g. `Add Mobvoi watch faces to catalog`),
with a body explaining the reasoning when it isn't obvious.

## Reporting bugs

Open an issue with:
- Watch model + Wear OS version (from the Diagnostics dashboard).
- What you did and what happened.
- The relevant lines from `~/.local/share/wearforge/wearforge.log` (run with
  `--verbose` to reproduce).

## Safety note

WearForge can disable and uninstall system packages. When adding features that
remove or modify things, default to the **reversible** path (`pm disable-user`
over `pm uninstall`), confirm destructive actions, and make sure the change is
recorded so the Restore menu can undo it.

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
