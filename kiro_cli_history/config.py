"""User configuration: a small JSON file under the platform's config directory."""

import json
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "kiro-cli-history"

# The type of any value a config key can hold.
ConfigValue = bool | int | str

# Known settings and their defaults. Keys are validated against this on `set`.
DEFAULTS: dict[str, ConfigValue] = {
    "scroll_top": False,
}


def get_config_path() -> Path:
    """Return the path to the user's config.json, creating its directory if needed."""
    config_dir = Path(user_config_dir(APP_NAME))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def load_config() -> dict[str, ConfigValue]:
    """Load the user config, merged over defaults. Falls back to defaults if invalid."""
    path = get_config_path()
    if not path.exists():
        return dict(DEFAULTS)
    try:
        with path.open() as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        return dict(DEFAULTS)
    if not isinstance(data, dict):
        return dict(DEFAULTS)
    return {**DEFAULTS, **data}


def save_config(config: dict[str, ConfigValue]) -> None:
    """Write the config dict to disk as JSON."""
    path = get_config_path()
    with path.open("w") as f:
        json.dump(config, f, indent=2, sort_keys=True)
        f.write("\n")


def coerce_value(key: str, raw_value: str) -> ConfigValue:
    """Coerce a CLI-provided string value to match the type of the key's default."""
    if key not in DEFAULTS:
        msg = f"Unknown config key: {key!r}. Known keys: {', '.join(sorted(DEFAULTS))}"
        raise ValueError(msg)
    default = DEFAULTS[key]
    if isinstance(default, bool):
        lowered = raw_value.strip().lower()
        if lowered in ("1", "true", "yes", "on"):
            return True
        if lowered in ("0", "false", "no", "off"):
            return False
        msg = f"Invalid boolean value for {key!r}: {raw_value!r}"
        raise ValueError(msg)
    if isinstance(default, int):
        return int(raw_value)
    return raw_value
