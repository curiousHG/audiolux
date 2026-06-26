"""Controller for the LEDDMX-03-1821 BLE strip.

Protocol (reverse-engineered + validated live against the strip):
  Universal frame:  7B FF <cmd> <d1> <d2> <d3> <d4> FF BF   (9 bytes)

  cmd 0x01  brightness   d1=level(0-31)  d2=level(0-100)  d3=00 d4=ff
  cmd 0x02  speed        d1=val(0-100)   d2=ff            d3=00 d4=ff
  cmd 0x03  effect mode  d1=mode(1..~200) d2=ff           d3=ff d4=ff
  cmd 0x04  power        d1=01/00        d2=ff            d3=ff d4=ff
  cmd 0x07  solid color  d1=G  d2=R  d3=B                 d4=00     (GRB order)
  cmd 0x0b  music style  d1=1..3         d2=00            d3=ff d4=ff
  cmd 0x0c  music sens.  d1=val(0-100)   d2=00            d3=ff d4=ff

Note: the controller's color order and pixel count are set in the app
(cmd 0x05 config). If colors look swapped, flip COLOR_ORDER below.

Usage:
  uv run python leddmx.py on|off
  uv run python leddmx.py color 255 0 128      |  red|green|blue|white|...
  uv run python leddmx.py bright 0..100
  uv run python leddmx.py mode <1..200> [speed 0..100]
  uv run python leddmx.py speed 0..100
  uv run python leddmx.py test
"""
import asyncio
import sys
from bleak import BleakClient, BleakScanner

TARGET_NAME = "LEDDMX-03-1821"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
COLOR_ORDER = "RGB"   # strip was reconfigured to GRBW/RGB order via the app (cmd 05)

NAMED = {
    "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
    "white": (255, 255, 255), "yellow": (255, 255, 0),
    "cyan": (0, 255, 255), "magenta": (255, 0, 255), "orange": (255, 90, 0),
}


def _frame(cmd, d1=0, d2=0, d3=0, d4=0):
    return bytes([0x7B, 0xFF, cmd, d1 & 0xFF, d2 & 0xFF, d3 & 0xFF, d4 & 0xFF, 0xFF, 0xBF])

def cmd_power(on):       return _frame(0x04, 0x01 if on else 0x00, 0xFF, 0xFF, 0xFF)
def cmd_brightness(pct): return _frame(0x01, round(pct * 31 / 100), pct, 0x00, 0xFF)   # pct 0..100
def cmd_speed(pct):      return _frame(0x02, pct, 0xFF, 0x00, 0xFF)                     # pct 0..100
def cmd_mode(m, sp=0xFF):return _frame(0x03, m, sp, 0xFF, 0xFF)
def cmd_sensitivity(pct):return _frame(0x0C, pct, 0x00, 0xFF, 0xFF)
def cmd_music_style(s):  return _frame(0x0B, s, 0x00, 0xFF, 0xFF)
def cmd_direction(fwd):  return _frame(0x0D, 1 if fwd else 0, 0xFF, 0xFF, 0xFF)  # 7B FF 0D <dir> ... BF

def cmd_color(r, g, b):
    d1, d2, d3 = (g, r, b) if COLOR_ORDER == "GRB" else (r, g, b)
    return _frame(0x07, d1, d2, d3, 0x00)


class LedDmx:
    def __init__(self, client):
        self.client = client
    async def _send(self, payload):
        await self.client.write_gatt_char(CHAR_UUID, payload, response=False)
    async def power(self, on):        await self._send(cmd_power(on))
    async def color(self, r, g, b):   await self._send(cmd_color(r, g, b))
    async def brightness(self, pct):  await self._send(cmd_brightness(pct))
    async def speed(self, pct):       await self._send(cmd_speed(pct))
    async def mode(self, m):          await self._send(cmd_mode(m))
    async def sensitivity(self, pct): await self._send(cmd_sensitivity(pct))


async def connect():
    dev = await BleakScanner.find_device_by_name(TARGET_NAME, timeout=15.0)
    if not dev:
        raise SystemExit("Device not found (is the phone still connected to the strip?).")
    return dev


async def run(args):
    dev = await connect()
    async with BleakClient(dev) as client:
        led = LedDmx(client)
        print(f"Connected to {dev.name}.")
        a = args[0] if args else "test"

        if a == "on":            await led.power(True)
        elif a == "off":         await led.power(False)
        elif a == "bright":      await led.brightness(int(args[1]))
        elif a == "speed":       await led.speed(int(args[1]))
        elif a == "mode":
            await led.mode(int(args[1]))
            if len(args) >= 3:
                await asyncio.sleep(0.1); await led.speed(int(args[2]))
        elif a == "color" and len(args) >= 4:
            await led.power(True); await asyncio.sleep(0.15)
            await led.color(*(int(x) for x in args[1:4]))
        elif a in NAMED:
            await led.power(True); await asyncio.sleep(0.15)
            await led.color(*NAMED[a])
        elif a == "test":
            for label, fn, fa in [
                ("ON", led.power, (True,)), ("RED", led.color, (255, 0, 0)),
                ("GREEN", led.color, (0, 255, 0)), ("BLUE", led.color, (0, 0, 255)),
                ("BRIGHT 100", led.brightness, (100,)), ("BRIGHT 20", led.brightness, (20,)),
                ("OFF", led.power, (False,))]:
                print(f"-> {label}"); await fn(*fa); await asyncio.sleep(1.5)
        else:
            raise SystemExit(f"Unknown command: {' '.join(args)}")
        await asyncio.sleep(0.3)
        print("Done.")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
