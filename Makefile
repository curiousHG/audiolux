.PHONY: install build run dev-api dev-web test clean

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

# --- development (two terminals) ---
# API with hot-reload:
dev-api:
	uv run audiolux
# Vite dev server with instant HMR (proxies /api + /media to :8765):
dev-web:
	cd frontend && npm run dev

# backend tests
test:
	uv run pytest -q

clean:
	rm -rf frontend/dist cache backend/__pycache__ backend/routers/__pycache__ tests/__pycache__
