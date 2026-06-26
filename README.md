# audiolux

Music-reactive controller for **LEDDMX-03** BLE LED strips. Drive solid colours,
the strip's 200+ built-in effect modes, brightness, speed and direction — by hand,
from the microphone, or from a YouTube track analysed offline and played in sync
(video embedded, lights driven by the song's own samples).

## Layout

```
backend/                FastAPI app + BLE control + DSP/MIR
  app.py                  assembles routers + static serving
  server.py               entry point (the `audiolux` console script)
  services.py             shared singletons (controller, engines, catalog, jobs)
  logging_config.py       central logging
  routers/                controls.py · music.py · tracks.py
  protocol.py             LEDDMX-03 9-byte wire protocol
  controller.py           async BLE connection, rate limiter, benchmark
  modes.py                mode catalog, families, mood->family, pick/resolve_mode
  music.py                live mic engine (loudness/beat/tempo/colour)
  ytsource.py             yt-dlp search + cached audio download
  analysis.py             librosa offline analysis -> light timeline
  player.py               track player (clocked by the browser video)
frontend/               React + Vite + TypeScript (Tailwind, `@/` -> src)
  src/hooks/              useStrip · useCatalog · useMusic
  src/components/         Header · Drawer · Player · Telemetry · …
tests/                  pytest suite
cache/                  downloaded audio + precomputed timelines (gitignored)
pyproject.toml          project + deps + `audiolux` script + pytest config
Makefile                install / build / run / dev / test
```

## Setup & run

Requires **ffmpeg** on PATH, plus `uv` and Node.

```sh
make install        # uv sync  +  npm install   (one time)
make run            # build frontend, then serve at http://localhost:8765
```

Equivalently, by hand:

```sh
uv sync
cd frontend && npm install && npm run build && cd ..
uv run audiolux            # http://localhost:8765
```

### Development (instant reload)

```sh
make dev-api        # FastAPI with hot-reload on :8765   (terminal 1)
make dev-web        # Vite HMR on :5173, proxies /api+/media -> :8765   (terminal 2)
```

### Tests

```sh
make test           # or: uv run pytest -q
```

### Notes

- Logging level via `AUDIOLUX_LOG` (default `INFO`): `AUDIOLUX_LOG=DEBUG uv run audiolux`.
- The first track after a server start pays a one-time ~30 s librosa/numba JIT
  warmup (kicked off in the background); every track after is a few seconds.
- Keep the phone disconnected from the strip so the app can hold the BLE link.
