"""Central logging setup. Level via the AUDIOLUX_LOG env var (default INFO)."""
import logging
import os

_CONFIGURED = False


def setup_logging():
    global _CONFIGURED
    if _CONFIGURED:
        return logging.getLogger("audiolux")
    level = os.environ.get("AUDIOLUX_LOG", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)-18s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # quiet noisy third parties
    for noisy in ("numba", "matplotlib", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _CONFIGURED = True
    return logging.getLogger("audiolux")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"audiolux.{name}")
