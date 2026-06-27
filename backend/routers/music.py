"""Microphone music-reactive engine."""
import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.services import engine, player

router = APIRouter(prefix="/api/music")


@router.get("/start")
async def music_start():
    """Start the mic-reactive engine (stopping the track player first)."""
    try:
        await player.stop()                 # only one source drives the strip
        engine.start(asyncio.get_running_loop())
        return {"ok": True, "sent": "music on"}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/stop")
async def music_stop():
    """Stop the mic-reactive engine."""
    await engine.stop()
    return {"ok": True, "sent": "music off"}


@router.get("/config")
async def music_config(react_bright: bool = None, react_speed: bool = None,
                       switch_modes: bool = None, use_direction: bool = None,
                       sensitivity: float = None, beats_per_switch: int = None,
                       bright_floor: int = None, smooth: float = None,
                       auto_family: bool = None, peak_strobe: bool = None, families: str = None):
    """Update mic-engine config (only non-None fields) and active families."""
    engine.configure(react_bright=react_bright, react_speed=react_speed,
                     switch_modes=switch_modes, use_direction=use_direction,
                     sensitivity=sensitivity, beats_per_switch=beats_per_switch,
                     bright_floor=bright_floor, smooth=smooth, auto_family=auto_family,
                     peak_strobe=peak_strobe)
    if families is not None:
        engine.set_families([f for f in families.split(",") if f])
    return {"ok": True, "cfg": engine.cfg, "active_families": engine.active_families}


@router.get("/state")
async def music_state():
    """Current mic-engine state."""
    return {"ok": True, **engine.state()}
