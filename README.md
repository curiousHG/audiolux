# audiolux

Music-reactive controller for **LEDDMX-03** BLE LED strips. Drive solid colours,
the strip's 200+ built-in effect modes, brightness, speed and direction — by hand,
from the microphone, or from a YouTube track analysed offline and played in sync.

## Layout

```
backend/      FastAPI app + BLE control + DSP/MIR
  protocol.py     LEDDMX-03 9-byte wire protocol
  controller.py   async BLE connection, rate limiter, benchmark
  modes.py        211-mode catalog, family classification, pick_mode
  music.py        live mic engine (loudness/beat/tempo/colour)
  ytsource.py     yt-dlp search + cached audio download
  analysis.py     librosa offline analysis -> light timeline
  player.py       track player, driven by the browser audio clock
  app.py          HTTP API + static serving
frontend/     React + Vite + TypeScript UI
cache/        downloaded audio + precomputed timelines (gitignored)
run.py        entry point
```

## Running

```sh
# 1. python deps (into .venv via uv)
uv pip install fastapi uvicorn bleak numpy sounddevice yt-dlp librosa soundfile

# 2. build the frontend (served by FastAPI at /)
cd frontend && npm install && npm run build && cd ..

# 3. start (hot-reload on; keep the phone disconnected from the strip)
uv run python run.py        # http://localhost:8765
```

For UI development with instant refresh, run `npm run dev` in `frontend/`
(proxies `/api` + `/media` to the backend on :8765).

Requires `ffmpeg` on PATH (for audio extraction).
