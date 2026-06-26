"""Server entry point. Exposed as the `audiolux` console script (see pyproject).

    uv run audiolux            # or:  uv run python run.py

Hot reload is on by default (edits to backend/*.py auto-restart). Disable with
LEDDMX_RELOAD=0. Keep the phone disconnected from the strip so we can hold it.
"""
import os
import webbrowser

import uvicorn

from backend.logging_config import get_logger, setup_logging


def main():
    setup_logging()
    log = get_logger("server")
    url = "http://localhost:8765"
    reload = os.environ.get("LEDDMX_RELOAD", "1") != "0"
    log.info("audiolux starting at %s (hot-reload=%s)", url, "on" if reload else "off")
    if not reload:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8765, log_level="warning",
                reload=reload, reload_dirs=["backend"])


if __name__ == "__main__":
    main()
