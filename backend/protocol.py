"""LEDDMX-03 BLE wire protocol.

Reverse-engineered from the "LED LAMP" app (LEDDMX-03 family). Every command is
a fixed 9-byte frame:

    7B FF <cmd> <d1> <d2> <d3> <d4> FF BF

    cmd 0x01  brightness   d1 = level*31/100, d2 = level(0-100), d3 = 0, d4 = ff
    cmd 0x02  speed        d1 = 0-100,        d2 = ff, d3 = 0, d4 = ff
    cmd 0x03  effect mode  d1 = mode(1-200),  d2..d4 = ff
    cmd 0x04  power        d1 = 1/0,          d2..d4 = ff
    cmd 0x07  solid color  d1..d3 = R,G,B (or G,R,B), d4 = 0
    cmd 0x0C  sensitivity  d1 = 0-100
    cmd 0x0D  direction    d1 = 1/0   (ignored by this firmware; use mode pairs)
"""

TARGET_NAME = "LEDDMX-03-1821"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
COLOR_ORDER = "RGB"   # "GRB" if red/green look swapped

HEADER = (0x7B, 0xFF)
FOOTER = (0xFF, 0xBF)


def _frame(cmd: int, d1=0, d2=0, d3=0, d4=0) -> bytes:
    """Build a 9-byte command frame: HEADER, cmd, four data bytes, FOOTER."""
    return bytes([*HEADER, cmd, d1 & 0xFF, d2 & 0xFF, d3 & 0xFF, d4 & 0xFF, *FOOTER])


def power(on: bool) -> bytes:
    """Frame to turn the strip on or off."""
    return _frame(0x04, 1 if on else 0, 0xFF, 0xFF, 0xFF)


def brightness(pct: int) -> bytes:
    """Frame to set brightness (0-100%)."""
    pct = max(0, min(100, int(pct)))
    return _frame(0x01, round(pct * 31 / 100), pct, 0x00, 0xFF)


def speed(pct: int) -> bytes:
    """Frame to set effect speed (0-100%)."""
    pct = max(0, min(100, int(pct)))
    return _frame(0x02, pct, 0xFF, 0x00, 0xFF)


def mode(m: int) -> bytes:
    """Frame to select effect mode (1-255)."""
    return _frame(0x03, max(1, min(255, int(m))), 0xFF, 0xFF, 0xFF)


def direction(forward: bool) -> bytes:
    """Frame to set effect direction (forward/reverse)."""
    return _frame(0x0D, 1 if forward else 0, 0xFF, 0xFF, 0xFF)


def sensitivity(pct: int) -> bytes:
    """Frame to set mic/audio sensitivity (0-100%)."""
    return _frame(0x0C, max(0, min(100, int(pct))), 0x00, 0xFF, 0xFF)


def color(r: int, g: int, b: int) -> bytes:
    """Frame to set a solid RGB color, honoring COLOR_ORDER."""
    d1, d2, d3 = (g, r, b) if COLOR_ORDER == "GRB" else (r, g, b)
    return _frame(0x07, d1, d2, d3, 0x00)
