"""Set the LEDDMX strip to a color and leave it on.

Usage:
  uv run python led_set.py blue
  uv run python led_set.py red
  uv run python led_set.py 255 0 255      # raw R G B
  uv run python led_set.py off
"""
import asyncio
import sys
from bleak import BleakClient, BleakScanner

TARGET_NAME = "LEDDMX-03-1821"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

NAMED = {
    "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
    "white": (255, 255, 255), "yellow": (255, 255, 0),
    "cyan": (0, 255, 255), "magenta": (255, 0, 255),
}


def power(on: bool) -> bytes:
    return bytes([0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01 if on else 0x00, 0xFF, 0x00, 0xEF])

def color(r, g, b) -> bytes:
    return bytes([0x7E, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xEF])


def parse_args(argv):
    if not argv:
        return ("color", NAMED["blue"])
    a = argv[0].lower()
    if a == "off":
        return ("off", None)
    if a in NAMED:
        return ("color", NAMED[a])
    if len(argv) >= 3:
        return ("color", tuple(int(x) for x in argv[:3]))
    raise SystemExit(f"Unknown color '{a}'. Try: {', '.join(NAMED)} | R G B | off")


async def main():
    mode, rgb = parse_args(sys.argv[1:])
    dev = await BleakScanner.find_device_by_name(TARGET_NAME, timeout=15.0)
    if not dev:
        raise SystemExit("Device not found / not in range.")
    async with BleakClient(dev) as client:
        print(f"Connected to {dev.name}.")
        if mode == "off":
            cmd = power(False)
            print(f"-> OFF  {cmd.hex()}")
            await client.write_gatt_char(CHAR_UUID, cmd, response=False)
        else:
            on = power(True)
            await client.write_gatt_char(CHAR_UUID, on, response=False)
            await asyncio.sleep(0.3)
            cmd = color(*rgb)
            print(f"-> ON + color rgb{rgb}  {cmd.hex()}")
            await client.write_gatt_char(CHAR_UUID, cmd, response=False)
        await asyncio.sleep(0.5)
        print("Done (color held).")


if __name__ == "__main__":
    asyncio.run(main())
