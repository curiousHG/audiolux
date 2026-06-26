"""Control the LEDDMX BLE strip over the FFE1 transparent-UART characteristic.

Tries the common '7E ... EF' framed protocol used by many FFE0/FFE1 LED/DMX
controllers. Runs a visible test sequence: ON -> red -> green -> blue -> OFF.
Watch the strip and note which steps (if any) take effect.
"""
import asyncio
import sys
from bleak import BleakClient, BleakScanner

TARGET_NAME = "LEDDMX-03-1821"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

# --- '7E..EF' protocol (ELK-BLE / MohuanLED / common DMX apps) ---
def power(on: bool) -> bytes:
    return bytes([0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01 if on else 0x00, 0xFF, 0x00, 0xEF])

def color(r: int, g: int, b: int) -> bytes:
    return bytes([0x7E, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xEF])


async def main():
    dev = await BleakScanner.find_device_by_name(TARGET_NAME, timeout=15.0)
    if not dev:
        print("Device not found / not in range.")
        sys.exit(1)
    print(f"Connecting to {dev.name} @ {dev.address}...")

    async with BleakClient(dev) as client:
        print("Connected.\n")

        def on_notify(_, data: bytearray):
            print(f"  <- notify: {data.hex()}")

        try:
            await client.start_notify(CHAR_UUID, on_notify)
        except Exception as e:
            print(f"  (notify unavailable: {e})")

        async def send(label: str, payload: bytes):
            print(f"-> {label:<12} {payload.hex()}")
            # response=False matches write-without-response; many strips need this
            await client.write_gatt_char(CHAR_UUID, payload, response=False)
            await asyncio.sleep(1.5)

        await send("POWER ON", power(True))
        await send("RED",   color(255, 0, 0))
        await send("GREEN", color(0, 255, 0))
        await send("BLUE",  color(0, 0, 255))
        await send("WHITE", color(255, 255, 255))
        await send("POWER OFF", power(False))

        print("\nSequence complete.")


if __name__ == "__main__":
    asyncio.run(main())
