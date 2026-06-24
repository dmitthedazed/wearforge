"""Unit tests for the pure (non-ADB, non-interactive) helpers in WearForge."""
import json
import os

import pytest

import wearforge as wf


# --- rec_badge -------------------------------------------------------------

def test_rec_badge_known_ratings():
    assert wf.rec_badge("Recommended")[0] == "REC "
    assert wf.rec_badge("safe")[0] == "SAFE"
    assert wf.rec_badge("EXPERT")[0] == "EXP "


def test_rec_badge_priority_ordering():
    # Lower priority = safer / more actionable, should sort first.
    p_rec = wf.rec_badge("recommended")[1]
    p_adv = wf.rec_badge("advanced")[1]
    p_exp = wf.rec_badge("expert")[1]
    p_unknown = wf.rec_badge("something-else")[1]
    assert p_rec < p_adv < p_exp < p_unknown


def test_rec_badge_unknown_is_fixed_width():
    badge, _ = wf.rec_badge(None)
    assert len(badge) == 4


# --- _truncate -------------------------------------------------------------

def test_truncate_short_string_unchanged():
    assert wf._truncate("hello", 80) == "hello"


def test_truncate_long_string_has_ellipsis():
    out = wf._truncate("x" * 100, 10)
    assert len(out) == 10
    assert out.endswith("…")


# --- friendly names --------------------------------------------------------

def test_get_friendly_name_uses_catalog():
    assert wf.get_friendly_name("com.samsung.android.bixby.agent") == "Bixby Voice Assistant"


def test_fallback_friendly_name_expands_tts():
    assert wf.get_fallback_friendly_name("com.google.android.tts") == "Text-to-Speech"


def test_fallback_friendly_name_non_empty():
    name = wf.get_fallback_friendly_name("com.example.someweirdpackage")
    assert name and name[0].isupper()


# --- make_pkg_choice -------------------------------------------------------

def test_make_pkg_choice_has_badge_and_value():
    choice = wf.make_pkg_choice("com.android.nfc", "NFC Service", "Expert", False)
    assert choice.title.startswith("EXP ")
    assert choice.value == "com.android.nfc"


def test_make_pkg_choice_marks_disabled():
    choice = wf.make_pkg_choice("com.android.nfc", "NFC", "Expert", True)
    assert choice.title.rstrip().endswith("✗")


def test_make_pkg_choice_drops_redundant_friendly_name():
    choice = wf.make_pkg_choice(
        "com.android.managedprovisioning", "Managedprovisioning", "Expert", False
    )
    assert "·" not in choice.title


def test_make_pkg_choice_keeps_informative_friendly_name():
    choice = wf.make_pkg_choice("com.google.android.apps.maps", "Google Maps", "Safe", False)
    assert "· Google Maps" in choice.title


def test_make_pkg_choice_collapses_description_whitespace():
    choice = wf.make_pkg_choice(
        "com.x.y", "Y", "Safe", False, description="line1\n  line2\t  line3"
    )
    assert choice.description == "line1 line2 line3"


# --- data dir resolution ---------------------------------------------------

def test_get_data_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("WEARFORGE_DATA_DIR", str(tmp_path / "custom"))
    assert wf.get_data_dir() == str(tmp_path / "custom")


def test_get_data_dir_expands_user(monkeypatch):
    monkeypatch.setenv("WEARFORGE_DATA_DIR", "~/wf-test-dir")
    out = wf.get_data_dir()
    assert os.path.isabs(out)
    assert out.endswith("wf-test-dir")


def test_get_data_dir_uses_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("WEARFORGE_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert wf.get_data_dir() == str(tmp_path / "wearforge")


def test_get_data_dir_default_location(monkeypatch):
    monkeypatch.delenv("WEARFORGE_DATA_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    out = wf.get_data_dir()
    assert out.endswith(os.path.join(".local", "share", "wearforge"))


# --- argument parsing ------------------------------------------------------

def test_parse_args_defaults():
    args = wf.parse_args([])
    assert args.device is None
    assert args.no_auto_connect is False
    assert args.update_uad is False
    assert args.verbose is False


def test_parse_args_flags():
    args = wf.parse_args(["--device", "192.168.1.5:5555", "--verbose", "--no-auto-connect"])
    assert args.device == "192.168.1.5:5555"
    assert args.verbose is True
    assert args.no_auto_connect is True


# --- json round trip -------------------------------------------------------

def test_save_and_load_json_round_trip(tmp_path):
    path = str(tmp_path / "data.json")
    payload = {"a": 1, "b": ["x", "y"]}
    wf.save_json(path, payload)
    assert wf.load_json(path) == payload


def test_load_json_missing_returns_empty(tmp_path):
    assert wf.load_json(str(tmp_path / "nope.json")) == {}
