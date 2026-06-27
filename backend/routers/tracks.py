"""YouTube source (search/download/analyse) + track player transport."""
import asyncio
import json
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend import analysis, ytsource
from backend.logging_config import get_logger
from backend.services import engine, jobs, player

router = APIRouter()
log = get_logger("track")


def _timeline_path(vid: str) -> str:
    """Path of the cached analysis timeline JSON for a video id."""
    return os.path.join(ytsource.CACHE_DIR, f"{vid}.json")


def _cached_timeline(vid: str):
    """Return a cached timeline only if it exists AND matches the current schema
    version (else None, so it gets re-analysed)."""
    timeline_path = _timeline_path(vid)
    if not os.path.exists(timeline_path):
        return None
    try:
        with open(timeline_path) as f:
            tl = json.load(f)
        return tl if tl.get("version") == analysis.VERSION else None
    except Exception:
        return None


async def _prepare(vid: str, title: str, dur: int):
    """Download, analyse (or load cached), and hand a track to the player."""
    job = jobs[vid]
    player.start_loading()
    try:
        track = {"id": vid, "title": title or vid, "uploader": "", "duration": dur}
        if not title:
            track = await asyncio.to_thread(ytsource.meta, vid)
        job["track"] = track

        job["state"] = "downloading"
        tlp = _timeline_path(vid)
        log.info("[%s] downloading '%s'", vid, track["title"])

        def prog(f):
            job["progress"] = round(f, 3)
        await asyncio.to_thread(ytsource.download, vid, prog)

        job["state"], job["progress"] = "analyzing", 1.0
        tl = _cached_timeline(vid)
        if tl is None:
            log.info("[%s] analysing audio…", vid)
            tl = await asyncio.to_thread(analysis.analyze, ytsource.audio_path(vid))
            with open(tlp, "w") as f:
                json.dump(tl, f)
        else:
            log.info("[%s] using cached timeline", vid)

        track["duration"] = track.get("duration") or tl["duration"]
        player.load(track, tl)
        job["state"] = "ready"
        log.info("[%s] ready", vid)
    except Exception as e:
        player.stop_loading()
        job["state"], job["error"] = "error", str(e)
        log.error("[%s] failed: %s", vid, e)


@router.get("/api/yt/search")
async def yt_search(q: str):
    """Search YouTube for tracks matching the query."""
    try:
        results = await asyncio.to_thread(ytsource.search, q)
        log.info("search '%s' -> %s results", q, len(results))
        return {"ok": True, "results": results}
    except Exception as e:
        log.error("search '%s' failed: %s", q, e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/yt/load")
async def yt_load(id: str, title: str = "", dur: int = 0):
    """Load a track: serve immediately if cached, else kick off a prepare job."""
    tl = _cached_timeline(id) if ytsource.is_cached(id) else None
    if tl is not None:
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


@router.get("/api/yt/status")
async def yt_status(id: str):
    """Progress/state of a track's download+analysis job."""
    job = jobs.get(id)
    if not job:
        return {"ok": True, "state": "none"}
    out = {"ok": True, "state": job["state"], "progress": job.get("progress", 0.0),
           "track": job.get("track")}
    if job.get("error"):
        out["error"] = job["error"]
    if job["state"] == "ready":
        out["audio_url"] = f"/media/{id}.mp3"
    return out


@router.get("/api/player/tick")
async def player_tick(t: float, playing: int = 1):
    """Advance the track player to time t (taking over from the mic engine)."""
    if playing and engine.running:
        await engine.stop()                 # track takes over from the mic engine
    await player.tick(t, bool(playing))
    return {"ok": True, **player.state()}


@router.get("/api/player/stop")
async def player_stop():
    """Stop the track player."""
    await player.stop()
    return {"ok": True}


@router.get("/api/player/state")
async def player_state():
    """Current track-player state."""
    return {"ok": True, **player.state()}


@router.get("/api/player/plan")
async def player_plan():
    """Full-song mode plan + downsampled brightness/colour signals for the
    timeline view. Recomputed automatically when the config changes."""
    p = player.ensure_plan()
    if not p:
        return {"ok": True, "loaded": False}
    return {"ok": True, "loaded": True, **p, **player.signals()}
