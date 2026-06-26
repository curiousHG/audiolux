"""Probe several known FFE1 LED protocols to identify which one this strip speaks.

Watch the strip. When you see ANY reaction (flicker, on/off, color), note the
PROTOCOL label and step printed just before it. Also prints any notify bytes.
"""
import asyncio
from bleak import BleakClient, BleakScanner

TARGET_NAME = "LEDDMX-03-1821"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"


# Each protocol: name -> dict of step-name -> bytes
PROTOCOLS = {
    "Triones/HappyLighting": {
        "POWER ON":  bytes([0xCC, 0x23, 0x33]),
        "RED":       bytes([0x56, 0xFF, 0x00, 0x00, 0x00, 0xF0, 0xAA]),
        "BLUE":      bytes([0x56, 0x00, 0x00, 0xFF, 0x00, 0xF0, 0xAA]),
        "POWER OFF": bytes([0xCC, 0x24, 0x33]),
    },
    "MagicHome/LEDBLE": {
        "POWER ON":  bytes([0x71, 0x23, 0x0F, 0xA3]),
        "RED":       bytes([0x31, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x0F, 0x3F]),
        "BLUE":      bytes([0x31, 0x00, 0x00, 0xFF, 0x00, 0x00, 0x0F, 0x3F]),
        "POWER OFF": bytes([0x71, 0x24, 0x0F, 0xA4]),
    },
    # SP-series addressable controllers (SP110E-style): cmd byte is last
    "SP110E-style": {
        "POWER TOGGLE": bytes([0x00, 0x00, 0x00, 0xAA]),
        "RED":          bytes([0xFF, 0x00, 0x00, 0x1E]),
        "BLUE":         bytes([0x00, 0x00, 0xFF, 0x1E]),
    },
}


async def main():
    dev = await BleakScanner.find_device_by_name(TARGET_NAME, timeout=15.0)
    if not dev:
        raise SystemExit("Device not found / not in range.")
    print(f"Connecting to {dev.name}...\n")

    async with BleakClient(dev) as client:
        def on_notify(_, data: bytearray):
            print(f"      <- notify: {data.hex()}")
        try:
            await client.start_notify(CHAR_UUID, on_notify)
        except Exception as e:
            print(f"(notify unavailable: {e})\n")

        for proto, steps in PROTOCOLS.items():
            # try both write modes per protocol
            for resp in (False, True):
                mode = "write-no-resp" if not resp else "write-with-resp"
                print(f"=== PROTOCOL: {proto}  [{mode}] ===")
                for step, payload in steps.items():
                    print(f"  -> {step:<13} {payload.hex()}")
                    try:
                        await client.write_gatt_char(CHAR_UUID, payload, response=resp)
                    except Exception as e:
                        print(f"     (write failed: {e})")
                        break
                    await asyncio.sleep(1.8)
                print()
        print("Probe complete.")


if __name__ == "__main__":
    asyncio.run(main())
