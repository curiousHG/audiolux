"""Shared fixtures + helpers for the audiolux test suite."""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import modes as M  # noqa: E402
from backend import protocol as P  # noqa: E402


@pytest.fixture(scope="session")
def catalog():
    return M.build_family_catalog(M.classify(M.load_modes()))


@pytest.fixture(scope="session")
def num2name():
    return {m["n"]: m["name"] for m in M.load_modes()}


class FakeController:
    """Records the frames that would be sent over BLE, without any hardware."""
    def __init__(self):
        self.sends = []
        self.max_rate = 1000

    async def send(self, payload, critical=True):
        self.sends.append(payload)

    def cmds(self, code):
        return [p for p in self.sends if p[2] == code]


def cmd_code(payload):
    return payload[2]   # 0x01 bright, 0x02 speed, 0x03 mode, 0x04 power, 0x07 colour


def make_timeline(moods, colors, n=80, bpm=120.0, bright=0.85):
    """A minimal synthetic timeline (beats every 0.5 s, dt=0.1 s)."""
    moods = moods if isinstance(moods, list) else [moods] * n
    colors = colors if isinstance(colors, list) else [colors] * n
    return {
        "version": 3, "sr": 22050, "duration": round(n * 0.1, 2), "bpm": bpm,
        "dt": 0.1, "fps": 10.0,
        "beats": [round(i * 0.5, 2) for i in range(int(n * 0.1 / 0.5) + 2)],
        "bright": [bright] * n,
        "color": colors,
        "centroid": [0.5] * n,
        "dir": [1] * n,
        "mood": moods,
        "spec": [[0.1] * 40 for _ in range(n)],
    }


def run(coro):
    return asyncio.run(coro)
