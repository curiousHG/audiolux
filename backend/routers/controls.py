"""Direct strip controls + status + throughput."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .. import modes as M
from ..services import controller, engine, player, GROUPED, FAMILIES

router = APIRouter()


async def _do(coro, **extra):
    """Run a controller coroutine, return a uniform JSON result."""
    try:
        await coro
        return {"ok": True, **extra}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/state")
async def state():
    return {"ok": True, "connected": controller.connected,
            "cmds": controller.stats(), "music": engine.state(), "player": player.state()}


@router.get("/api/modes")
async def modes():
    return {"ok": True, "groups": GROUPED}


@router.get("/api/families")
async def families():
    return {"ok": True, "families": FAMILIES, "freq_colors": M.FREQ_COLORS,
            "color_hex": M.COLOR_HEX, "bar_colors": engine.bar_colors}


@router.get("/api/power")
async def power(on: int = 1):
    return await _do(controller.power(bool(on)), sent=f"power {'on' if on else 'off'}")


@router.get("/api/color")
async def color(hex: str):
    h = hex.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    await controller.power(True)
    return await _do(controller.color(r, g, b), sent=f"color {r},{g},{b}")


@router.get("/api/bright")
async def bright(v: int):
    return await _do(controller.brightness(v), sent=f"brightness {v}")


@router.get("/api/speed")
async def speed(v: int):
    return await _do(controller.speed(v), sent=f"speed {v}")


@router.get("/api/mode")
async def mode(m: int):
    return await _do(controller.mode(m), sent=f"mode {m}")


@router.get("/api/benchmark")
async def benchmark(n: int = 120):
    try:
        return {"ok": True, **(await controller.benchmark(n))}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/maxrate")
async def maxrate(r: float):
    controller.set_max_rate(r)
    return {"ok": True, "max_rate": controller.max_rate}
