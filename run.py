"""Entry point: start the LEDDMX web controller.

    uv run python run.py

Then open http://localhost:8765  (keep the phone disconnected from the strip).

Hot reload is on by default: edits to backend/*.py auto-restart the server.
Edits to static/ (HTML/CSS/JS) are served from disk — just refresh the browser.
Disable reload with  LEDDMX_RELOAD=0 uv run python run.py
"""
import os
import webbrowser

import uvicorn

if __name__ == "__main__":
    url = "http://localhost:8765"
    reload = os.environ.get("LEDDMX_RELOAD", "1") != "0"
    print(f"LEDDMX Control running at {url}  (hot-reload={'on' if reload else 'off'}, Ctrl+C to stop)")
    if not reload:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8765, log_level="warning",
                reload=reload, reload_dirs=["backend"])
