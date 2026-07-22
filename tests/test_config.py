"""Tests for the JSON user config module."""

import json
from pathlib import Path

import pytest

from kiro_cli_history import config as config_module
from kiro_cli_history.config import coerce_value, load_config, save_config


@pytest.fixture(autouse=True)
def _isolated_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect the config path to a temp directory for every test in this file."""
    monkeypatch.setattr(config_module, "user_config_dir", lambda _name: str(tmp_path))


def test_load_config_defaults_when_missing() -> None:
    """With no config file present, load_config returns the defaults."""
    assert load_config() == {"scroll_top": False}


def test_save_and_load_roundtrip() -> None:
    """A saved config value is read back correctly, merged with defaults."""
    save_config({"scroll_top": True})
    assert load_config() == {"scroll_top": True}


def test_load_config_ignores_corrupt_file() -> None:
    """A malformed config file falls back to defaults instead of raising."""
    path = config_module.get_config_path()
    path.write_text("not valid json{{{")
    assert load_config() == {"scroll_top": False}


def test_coerce_value_bool() -> None:
    """Boolean-like strings are coerced to real booleans."""
    assert coerce_value("scroll_top", "true") is True
    assert coerce_value("scroll_top", "0") is False


def test_coerce_value_unknown_key_raises() -> None:
    """Unknown config keys raise a ValueError with a helpful message."""
    with pytest.raises(ValueError, match="Unknown config key"):
        coerce_value("nonexistent", "1")


def test_coerce_value_invalid_bool_raises() -> None:
    """Non-boolean-like strings for a boolean key raise a ValueError."""
    with pytest.raises(ValueError, match="Invalid boolean value"):
        coerce_value("scroll_top", "maybe")


def test_save_config_writes_json() -> None:
    """The config file on disk is valid, human-readable JSON."""
    save_config({"scroll_top": True})
    on_disk = json.loads(config_module.get_config_path().read_text())
    assert on_disk == {"scroll_top": True}
