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
    return {
        "params": {k: v["value"] for k, v in params.PARAMS.items()},
        "cfg": dict(engine.cfg),
        "families": list(engine.active_families),
    }


def apply(data: dict):
    for k, v in (data.get("params") or {}).items():
        params.set_value(k, v)
    engine.configure(**{k: v for k, v in (data.get("cfg") or {}).items() if k in engine.cfg})
    if data.get("families"):
        engine.set_families(data["families"])


def save(name: str, data: dict):
    with open(os.path.join(CONFIG_DIR, f"{name}.json"), "w") as f:
        json.dump(data, f, indent=2)


def load(name: str):
    p = os.path.join(CONFIG_DIR, f"{name}.json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def delete(name: str):
    p = os.path.join(CONFIG_DIR, f"{name}.json")
    if os.path.exists(p):
        os.remove(p)


def names() -> list:
    return sorted(f[:-5] for f in os.listdir(CONFIG_DIR) if f.endswith(".json"))


# factory snapshot, captured once at import (params + cfg are at their defaults here)
DEFAULTS = current()
