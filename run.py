"""Convenience launcher — equivalent to the `audiolux` console script.

    uv run python run.py        # then open http://localhost:8765

Hot reload is on by default (edits to backend/*.py). Disable with LEDDMX_RELOAD=0.
"""
from backend.server import main

if __name__ == "__main__":
    main()
