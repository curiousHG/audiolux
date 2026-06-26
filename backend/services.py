"""Shared singletons used across the API routers: the BLE controller, the mic +
track engines, the mode catalog, and the in-flight download/analysis job table."""
from . import modes as M
from .controller import LedController
from .music import MusicEngine
from .player import PlayerEngine

MODES = M.load_modes()
GROUPED = M.classify(MODES)
CATALOG = M.build_family_catalog(GROUPED)
FAMILIES = M.selectable_families(CATALOG)

controller = LedController()
engine = MusicEngine(controller, CATALOG)
player = PlayerEngine(controller, engine)

# youtube id -> {state, progress, track, error}
jobs: dict[str, dict] = {}
