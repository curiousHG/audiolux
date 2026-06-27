"""Named configs = algorithm params + engine cfg + selected families. Saved to
configs/*.json. "Default" is the built-in factory snapshot (captured at startup)."""
import json
import os

from backend import params
from backend.services import engine

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(_HERE, "configs")
os.makedirs(CONFIG_DIR, exist_ok=True)


def current() -> dict:
    """Snapshot the live params, engine cfg, and selected families as a config dict."""
    return {
        "params": {name: p.value for name, p in params.PARAMS.items()},
        "cfg": dict(engine.cfg),
        "families": list(engine.active_families),
    }


def apply(data: dict):
    """Apply a saved config dict back onto the live params, engine cfg, and families."""
    for k, v in (data.get("params") or {}).items():
        params.set_value(k, v)
    engine.configure(**{k: v for k, v in (data.get("cfg") or {}).items() if k in engine.cfg})
    if data.get("families"):
        engine.set_families(data["families"])


def save(name: str, data: dict):
    """Write a config dict to configs/<name>.json."""
    with open(os.path.join(CONFIG_DIR, f"{name}.json"), "w") as f:
        json.dump(data, f, indent=2)


def load(name: str):
    """Read configs/<name>.json, or None if it doesn't exist."""
    config_path = os.path.join(CONFIG_DIR, f"{name}.json")
    if not os.path.exists(config_path):
        return None
    with open(config_path) as f:
        return json.load(f)


def delete(name: str):
    """Remove configs/<name>.json if present."""
    config_path = os.path.join(CONFIG_DIR, f"{name}.json")
    if os.path.exists(config_path):
        os.remove(config_path)


def names() -> list:
    """List saved config names (sorted, without the .json suffix)."""
    return sorted(f[:-5] for f in os.listdir(CONFIG_DIR) if f.endswith(".json"))


# factory snapshot, captured at import while params/cfg are still at defaults
DEFAULTS = current()
