"""FastAPI application: assembles the routers + static serving.

Route handlers live in backend/routers/ (controls, music, tracks); shared
singletons (controller, engines, catalog, jobs) live in backend/services.py.
"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend import analysis, ytsource
from backend.logging_config import get_logger, setup_logging
from backend.routers import controls, music, tracks
from backend.services import controller, engine

setup_logging()
log = get_logger("app")

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(_HERE, "static")
DIST_DIR = os.path.join(_HERE, "frontend", "dist")
# serve the built React app when present, else the legacy static/ folder
FRONTEND_DIR = DIST_DIR if os.path.exists(os.path.join(DIST_DIR, "index.html")) else STATIC_DIR


async def _warmup():
    log.info("warming up librosa (numba JIT)…")
    await asyncio.to_thread(analysis.warmup)
    log.info("librosa warmup complete — first track will analyse fast")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("serving frontend from %s", os.path.relpath(FRONTEND_DIR, _HERE))
    asyncio.create_task(_warmup())
    yield
    log.info("shutting down")
    await engine.stop()
    await controller.disconnect()


app = FastAPI(title="LEDDMX Control", lifespan=lifespan)

app.include_router(controls.router)
app.include_router(music.router)
app.include_router(tracks.router)

# static media + frontend (mounted last so /api/* wins)
app.mount("/media", StaticFiles(directory=ytsource.CACHE_DIR), name="media")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="root")
