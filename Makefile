.PHONY: install build run dev dev-api dev-web watch test clean

# one-time setup: python deps (uv) + frontend deps (npm). Needs ffmpeg on PATH.
install:
	uv sync
	cd frontend && npm install

# build the frontend; FastAPI then serves frontend/dist at /
build:
	cd frontend && npm run build

# run the app (serves the built frontend). http://localhost:8765
run: build
	uv run audiolux

# --- development ---
# ONE URL (http://localhost:8765) and ONE terminal: backend (auto-restart on .py
# changes) + frontend dist watcher, with interleaved, colour-prefixed logs.
# Ctrl+C stops both. Just reload the browser to see frontend changes.
dev:
	cd frontend && npx concurrently -k -n api,web -c cyan,magenta \
	  "cd $(CURDIR) && uv run audiolux" \
	  "npm run watch"

# or run the pieces yourself:
dev-api:        # FastAPI with hot-reload (like Django runserver)
	uv run audiolux
watch:          # rebuild frontend/dist on every save -> reload browser to see
	cd frontend && npm run watch
dev-web:        # alternative: Vite dev server on :5173 with instant HMR
	cd frontend && npm run dev

# backend tests
test:
	uv run pytest -q

clean:
	rm -rf frontend/dist cache backend/__pycache__ backend/routers/__pycache__ tests/__pycache__
