"""Algorithm explainer, live param tuning, and config save/load."""
import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend import analysis, configs, modes as M, params, player as playermod, ytsource
from backend.services import engine, player

router = APIRouter()


async def _reanalyse() -> bool:
    """Re-run the offline analysis on the loaded track with the current params."""
    if player.loaded and player.track and ytsource.is_cached(player.track["id"]):
        tl = await asyncio.to_thread(analysis.analyze, ytsource.audio_path(player.track["id"]))
        player.load(player.track, tl)
        return True
    return False


@router.get("/api/explain")
async def explain():
    """Everything the 'how it works' panel needs — the actual params + mappings."""
    return {
        "ok": True,
        "params": params.as_dict(),
        "cfg": engine.cfg,
        "families": engine.active_families,
        "freq_colors": M.FREQ_COLORS,
        "color_hex": M.COLOR_HEX,
        "mood_names": M.MOOD_NAMES,
        "mood_families": M.MOOD_FAMILIES,
        "speed": {"min": playermod.SPEED_MIN, "max": playermod.SPEED_MAX,
                  "tempo_w": playermod.TEMPO_W, "drive_w": playermod.DRIVE_W},
        "dsp": {"sr": analysis.SR, "n_fft": analysis.NFFT, "hop": analysis.HOP,
                "nbars": analysis.NBARS, "fps": round(analysis.SR / analysis.HOP, 1)},
        "configs": ["Default"] + configs.names(),
    }


@router.get("/api/tune")
async def tune(name: str, value: float):
    """Set one algorithm param, re-analysing the loaded track if it's offline-affecting."""
    if not params.set_value(name, value):
        return JSONResponse({"ok": False, "error": f"unknown param '{name}'"}, status_code=400)
    reanalysed = await _reanalyse() if params.PARAMS[name].reanalyse else False
    return {"ok": True, "name": name, "value": params.get(name), "reanalysed": reanalysed}


@router.get("/api/configs")
async def list_configs():
    """List saved config names alongside the current live config."""
    return {"ok": True, "configs": ["Default"] + configs.names(), **configs.current()}


@router.get("/api/config/save")
async def save_config(name: str):
    """Save the current live config under the given name."""
    configs.save(name, configs.current())
    return {"ok": True, "configs": ["Default"] + configs.names()}


@router.get("/api/config/load")
async def load_config(name: str):
    """Load a saved (or the Default) config and re-analyse the loaded track."""
    data = configs.DEFAULTS if name == "Default" else configs.load(name)
    if data is None:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    configs.apply(data)
    reanalysed = await _reanalyse()
    return {"ok": True, "reanalysed": reanalysed, **configs.current()}


@router.get("/api/config/delete")
async def delete_config(name: str):
    """Delete a saved config by name."""
    configs.delete(name)
    return {"ok": True, "configs": ["Default"] + configs.names()}
