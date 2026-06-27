# audiolux

Music-reactive controller for **LEDDMX-03** BLE LED strips.

Drive solid colours, the strip's 200+ built-in effect modes, brightness, speed and
direction — by hand, from the microphone, or from a **YouTube track analysed offline
and played in perfect sync**: the video plays in the browser and the lights are driven
by the song's own analysed samples (so room/fan noise never reaches the lights).

Everything the engine decides — colour, mode, brightness, speed, direction, strobe —
is computed from the audio and shown live in the UI, with a **"How it works"** page
that diagrams the whole pipeline and links each step back to the code.

---

## Requirements

- **Python 3.11 or 3.12**, with [`uv`](https://docs.astral.sh/uv/) installed.
- **Node.js 18+** (for the React/Vite frontend).
- **ffmpeg** on your `PATH` (yt-dlp uses it to extract audio).
- A **LEDDMX-03** BLE strip in range, **not currently held by the phone app**
  (only one device can own the BLE link at a time).
- **Bluetooth permission** for your terminal/app (macOS: System Settings →
  Privacy & Security → Bluetooth). Mic input permission too, if you use the live
  mic engine.

> The target device name is `LEDDMX-03-1821` in `backend/protocol.py`
> (`TARGET_NAME`). If your strip advertises a different name, change it there.
> If red/green look swapped, flip `COLOR_ORDER` to `"GRB"` in the same file.

---

## Setup & run

```sh
make install        # uv sync  +  npm install   (one time)
make run            # build the frontend, then serve at http://localhost:8765
```

Then open **http://localhost:8765**. A default track (Gojira – Stranded) preloads;
search YouTube, pick a song, and it downloads + analyses in the background and starts
driving the strip in sync.

By hand, equivalently:

```sh
uv sync
cd frontend && npm install && npm run build && cd ..
uv run audiolux            # http://localhost:8765
```

### Development (auto-reload, one terminal)

```sh
make dev            # http://localhost:8765
```

- **Backend** hot-reloads on any `backend/*.py` change (uvicorn `reload=True`).
- **Frontend** `dist/` rebuilds on save (`vite build --watch`) — reload the browser.

Prefer instant HMR? `make dev-web` runs the Vite dev server on `:5173` (proxying
`/api` + `/media` to `:8765`); pair it with `make dev-api`.

### Tests

```sh
make test           # or: uv run pytest -q
```

---

## Using it

- **Player** — search/play a YouTube track; the lights follow the analysed song.
  *Smart* picks the effect family from the music's mood; *Strobe* flashes on peaks.
  Tune the algorithm constants live from the sliders beside the video — changes
  re-analyse the loaded track and recolour the strip within a fraction of a second.
- **Controls** — manual colour, brightness, speed, effect mode/direction, a
  soundboard, and the live **mic engine** (reacts to the room instead of a track).
- **How it works** — the full audio → strip pipeline as a flow graph, with each
  step linked to the function/file that implements it, plus the live math.

---

## How it works (in one breath)

```
YouTube audio → resample 44.1kHz → STFT
  ├─ RMS → loudness ─→ brightness (full-range) · mood · direction
  ├─ whitened bands → dominant colour
  └─ onset → beats → trailing tempo → speed ; onset → drive → speed
  mood → effect family ; peak → colour strobe ; family+colour → mode #
  {mode, brightness, speed, strobe} → reconciler (coarsen to command rate)
        → BLE 9-byte frames → LED strip
```

The strip accepts only ~14 commands/sec, so the player computes the *ideal* command
for every frame and spends that budget on whatever has drifted furthest. See
`docs/MODES.md` for what each of the strip's effect modes actually does.

---

## Layout

```
backend/                FastAPI app + BLE control + DSP/MIR
  server.py               entry point (the `audiolux` console script)
  app.py                  assembles routers + static serving
  services.py             shared singletons (controller, engines, catalog, jobs)
  routers/                controls · music · tracks · settings
  protocol.py             LEDDMX-03 9-byte wire protocol
  controller.py           async BLE connection, rate limiter, benchmark
  modes.py                mode catalog, families, mood→family, resolve_mode
  music.py                live mic engine (loudness/beat/tempo/colour)
  ytsource.py             yt-dlp search + cached audio download
  analysis.py             librosa offline analysis → light timeline
  dsp.py                  generic signal helpers (ema, smooth)
  planner.py              full-song mode plan (followed by the player + drawn by UI)
  player.py               track player + command reconciler (clocked by the video)
  params.py               runtime-tunable params (Param dataclass) surfaced to the UI
frontend/               React + Vite + TypeScript (Tailwind, `@/` → src)
  src/components/         Player · Telemetry · TrackTimeline · Tuning · HowItWorks · …
docs/MODES.md           what each LEDDMX-03 effect mode actually does
tests/                  pytest suite
cache/                  downloaded audio + precomputed timelines (gitignored)
Makefile                install / build / run / dev / test
```

---

## Notes

- Logging level via `AUDIOLUX_LOG` (default `INFO`): `AUDIOLUX_LOG=DEBUG uv run audiolux`.
- The first track after a server start pays a one-time ~30 s librosa/numba JIT
  warmup (kicked off in the background); every track after is a few seconds.
- Keep the phone disconnected from the strip so the app can hold the BLE link. If a
  hot-reload leaves a stale connection, the controller transparently reconnects.
- Downloaded audio is cached under `cache/` and re-used; it is **not** committed.

---

This project drives third-party hardware over a reverse-engineered BLE protocol and
downloads audio for **personal, offline** analysis — use it accordingly.
