"""Connect to the LEDDMX device and dump all GATT services/characteristics."""
import asyncio
import sys
from bleak import BleakClient, BleakScanner

TARGET_NAME = "LEDDMX-03-1821"


async def main():
    print(f"Looking for {TARGET_NAME}...")
    dev = await BleakScanner.find_device_by_name(TARGET_NAME, timeout=15.0)
    if not dev:
        print("Not found. Make sure it's powered and in range.")
        sys.exit(1)

    print(f"Found {dev.name} @ {dev.address}. Connecting...\n")
    async with BleakClient(dev) as client:
        print(f"Connected: {client.is_connected}\n")
        for service in client.services:
            print(f"[service] {service.uuid}  ({service.description})")
            for ch in service.characteristics:
                props = ",".join(ch.properties)
                print(f"   [char] {ch.uuid}  props=({props})")
                for d in ch.descriptors:
                    print(f"       [desc] {d.uuid}")
        print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
