"""FastAPI backend for the LEDDMX web controller."""
import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import analysis
from . import modes as M
from . import ytsource
from .controller import LedController
from .music import MusicEngine
from .player import PlayerEngine

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(_HERE, "static")
DIST_DIR = os.path.join(_HERE, "frontend", "dist")
# serve the built React app when present, else the legacy static/ folder
FRONTEND_DIR = DIST_DIR if os.path.exists(os.path.join(DIST_DIR, "index.html")) else STATIC_DIR

MODES = M.load_modes()
GROUPED = M.classify(MODES)
CATALOG = M.build_family_catalog(GROUPED)
FAMILIES = M.selectable_families(CATALOG)

controller = LedController()
engine = MusicEngine(controller, CATALOG)
player = PlayerEngine(controller, engine)

# in-flight download/analysis jobs, keyed by youtube id
jobs: dict[str, dict] = {}


def _timeline_path(vid: str) -> str:
    return os.path.join(ytsource.CACHE_DIR, f"{vid}.json")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(asyncio.to_thread(analysis.warmup))   # JIT librosa in the background
    yield
    await engine.stop()
    await controller.disconnect()


app = FastAPI(title="LEDDMX Control", lifespan=lifespan)


async def _do(coro, **extra):
    """Run a controller coroutine, return a uniform JSON result."""
    try:
        await coro
        return {"ok": True, **extra}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ---------- basic controls ----------
@app.get("/api/state")
async def state():
    return {"ok": True, "connected": controller.connected,
            "cmds": controller.stats(), "music": engine.state(), "player": player.state()}


@app.get("/api/modes")
async def modes():
    return {"ok": True, "groups": GROUPED}


@app.get("/api/families")
async def families():
    return {"ok": True, "families": FAMILIES, "freq_colors": M.FREQ_COLORS,
            "color_hex": M.COLOR_HEX, "bar_colors": engine.bar_colors}


@app.get("/api/power")
async def power(on: int = 1):
    return await _do(controller.power(bool(on)), sent=f"power {'on' if on else 'off'}")


@app.get("/api/color")
async def color(hex: str):
    h = hex.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    await controller.power(True)
    return await _do(controller.color(r, g, b), sent=f"color {r},{g},{b}")


@app.get("/api/bright")
async def bright(v: int):
    return await _do(controller.brightness(v), sent=f"brightness {v}")


@app.get("/api/speed")
async def speed(v: int):
    return await _do(controller.speed(v), sent=f"speed {v}")


@app.get("/api/mode")
async def mode(m: int):
    return await _do(controller.mode(m), sent=f"mode {m}")


# ---------- mic music engine ----------
@app.get("/api/music/start")
async def music_start():
    try:
        await player.stop()                 # only one source drives the strip
        engine.start(asyncio.get_running_loop())
        return {"ok": True, "sent": "music on"}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/music/stop")
async def music_stop():
    await engine.stop()
    return {"ok": True, "sent": "music off"}


@app.get("/api/music/config")
async def music_config(react_bright: bool = None, react_speed: bool = None,
                       switch_modes: bool = None, use_direction: bool = None,
                       sensitivity: float = None, beats_per_switch: int = None,
                       bright_floor: int = None, smooth: float = None,
                       families: str = None):
    engine.configure(react_bright=react_bright, react_speed=react_speed,
                     switch_modes=switch_modes, use_direction=use_direction,
                     sensitivity=sensitivity, beats_per_switch=beats_per_switch,
                     bright_floor=bright_floor, smooth=smooth)
    if families is not None:
        engine.set_families([f for f in families.split(",") if f])
    return {"ok": True, "cfg": engine.cfg, "active_families": engine.active_families}


@app.get("/api/music/state")
async def music_state():
    return {"ok": True, **engine.state()}


# ---------- youtube source: search / load / status ----------
@app.get("/api/yt/search")
async def yt_search(q: str):
    try:
        return {"ok": True, "results": await asyncio.to_thread(ytsource.search, q)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


async def _prepare(vid: str, title: str, dur: int):
    job = jobs[vid]
    try:
        track = {"id": vid, "title": title or vid, "uploader": "", "duration": dur}
        if not title:
            track = await asyncio.to_thread(ytsource.meta, vid)
        job["track"] = track

        job["state"] = "downloading"
        tlp = _timeline_path(vid)

        def prog(f):
            job["progress"] = round(f, 3)
        await asyncio.to_thread(ytsource.download, vid, prog)

        job["state"], job["progress"] = "analyzing", 1.0
        if os.path.exists(tlp):
            with open(tlp) as f:
                tl = json.load(f)
        else:
            tl = await asyncio.to_thread(analysis.analyze, ytsource.audio_path(vid))
            with open(tlp, "w") as f:
                json.dump(tl, f)

        track["duration"] = track.get("duration") or tl["duration"]
        player.load(track, tl)
        job["state"] = "ready"
    except Exception as e:
        job["state"], job["error"] = "error", str(e)


@app.get("/api/yt/load")
async def yt_load(id: str, title: str = "", dur: int = 0):
    # fully cached -> ready immediately
    if os.path.exists(_timeline_path(id)) and ytsource.is_cached(id):
        with open(_timeline_path(id)) as f:
            tl = json.load(f)
        track = {"id": id, "title": title or id, "uploader": "", "duration": dur or tl["duration"]}
        player.load(track, tl)
        jobs[id] = {"state": "ready", "progress": 1.0, "track": track}
        return {"ok": True, "id": id, "state": "ready"}
    cur = jobs.get(id, {}).get("state")
    if cur in ("starting", "downloading", "analyzing"):
        return {"ok": True, "id": id, "state": cur}
    jobs[id] = {"state": "starting", "progress": 0.0,
                "track": {"id": id, "title": title, "duration": dur}}
    asyncio.create_task(_prepare(id, title, dur))
    return {"ok": True, "id": id, "state": "starting"}


@app.get("/api/yt/status")
async def yt_status(id: str):
    j = jobs.get(id)
    if not j:
        return {"ok": True, "state": "none"}
    out = {"ok": True, "state": j["state"], "progress": j.get("progress", 0.0),
           "track": j.get("track")}
    if j.get("error"):
        out["error"] = j["error"]
    if j["state"] == "ready":
        out["audio_url"] = f"/media/{id}.mp3"
    return out


# ---------- player transport (clocked by the browser <audio>) ----------
@app.get("/api/player/tick")
async def player_tick(t: float, playing: int = 1):
    if playing and engine.running:
        await engine.stop()                 # track takes over from the mic
    await player.tick(t, bool(playing))
    return {"ok": True, **player.state()}


@app.get("/api/player/stop")
async def player_stop():
    await player.stop()
    return {"ok": True}


@app.get("/api/player/state")
async def player_state():
    return {"ok": True, **player.state()}


# ---------- throughput ----------
@app.get("/api/benchmark")
async def benchmark(n: int = 120):
    try:
        return {"ok": True, **(await controller.benchmark(n))}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/maxrate")
async def maxrate(r: float):
    controller.set_max_rate(r)
    return {"ok": True, "max_rate": controller.max_rate}


# ---------- static media + frontend (mounted last so /api/* wins) ----------
app.mount("/media", StaticFiles(directory=ytsource.CACHE_DIR), name="media")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="root")
