"""Scan for nearby BLE devices and print name + advertised services."""
import asyncio
from bleak import BleakScanner


async def main(duration: float = 8.0):
    print(f"Scanning for BLE devices for {duration:.0f}s...\n")
    devices = await BleakScanner.discover(timeout=duration, return_adv=True)

    rows = []
    for addr, (dev, adv) in devices.items():
        name = dev.name or adv.local_name or "(no name)"
        rows.append((adv.rssi if adv.rssi is not None else -999, name, addr, adv))

    rows.sort(reverse=True)  # strongest signal first
    for rssi, name, addr, adv in rows:
        print(f"{rssi:>4} dBm  {name:<28} {addr}")
        if adv.service_uuids:
            print(f"            services: {', '.join(adv.service_uuids)}")
        if adv.manufacturer_data:
            md = {hex(k): v.hex() for k, v in adv.manufacturer_data.items()}
            print(f"            mfr_data: {md}")
    print(f"\nTotal: {len(rows)} devices")


if __name__ == "__main__":
    asyncio.run(main())
