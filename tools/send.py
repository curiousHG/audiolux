"""Send arbitrary frames to the LEDDMX strip, one connection, labeled + paused.

Usage:
  uv run python send.py "LABEL=7bff07ff000000ffbf" "LABEL2=..."
  uv run python send.py 7bff07ff000000ffbf            # bare hex, auto-labeled
Optional first arg: --gap <seconds>  (default 2.5)
"""
import asyncio
import sys
from bleak import BleakClient, BleakScanner

TARGET_NAME = "LEDDMX-03-1821"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"


async def main(items, gap):
    dev = await BleakScanner.find_device_by_name(TARGET_NAME, timeout=15.0)
    if not dev:
        raise SystemExit("Device not found (is the phone still connected to it?).")
    async with BleakClient(dev) as client:
        print(f"Connected to {dev.name}.\n")

        def on_notify(_, data):
            print(f"      <- notify: {data.hex()}")
        try:
            await client.start_notify(CHAR_UUID, on_notify)
        except Exception:
            pass

        for i, (label, hexstr) in enumerate(items):
            payload = bytes.fromhex(hexstr)
            print(f"[{i+1}/{len(items)}] {label:<22} -> {payload.hex()}")
            await client.write_gatt_char(CHAR_UUID, payload, response=False)
            await asyncio.sleep(gap)
        await asyncio.sleep(0.4)
        print("\nDone.")


if __name__ == "__main__":
    args = sys.argv[1:]
    gap = 2.5
    if args and args[0] == "--gap":
        gap = float(args[1]); args = args[2:]
    items = []
    for i, a in enumerate(args):
        if "=" in a:
            label, hexstr = a.split("=", 1)
        else:
            label, hexstr = f"frame{i+1}", a
        items.append((label, hexstr.replace(" ", "")))
    asyncio.run(main(items, gap))
