"""Async BLE controller — one persistent connection, serialized writes, a rate
limiter (so we never exceed the strip's capacity), command telemetry, and a
benchmark that measures the strip's real acceptance rate via acknowledged writes."""
import asyncio
import collections
import time

from bleak import BleakClient, BleakScanner

from backend import protocol as P
from backend.logging_config import get_logger

log = get_logger("ble")


class LedController:
    def __init__(self):
        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()
        self._count = 0
        self._dropped = 0
        self._stamps = collections.deque(maxlen=4000)
        self._last_send_t = 0.0
        self.max_rate = 14.0                 # non-critical commands/sec ceiling

    @property
    def connected(self) -> bool:
        return bool(self._client and self._client.is_connected)

    def set_max_rate(self, r):
        self.max_rate = max(1.0, float(r))

    def stats(self, window: float = 20.0, bucket: float = 0.5):
        now = time.monotonic()
        while self._stamps and now - self._stamps[0] > window:
            self._stamps.popleft()
        nb = int(window / bucket)
        hist = [0] * nb
        for t in self._stamps:
            i = int((now - t) / bucket)
            if 0 <= i < nb:
                hist[i] += 1
        hist.reverse()
        rate = sum(1 for t in self._stamps if now - t <= 1.0)
        return {"total": self._count, "dropped": self._dropped, "rate": rate,
                "hist": hist, "bucket": bucket, "max_rate": self.max_rate}

    async def _reset(self):
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self._client = None

    async def _ensure(self):
        if self.connected:
            return
        log.info("scanning for %s…", P.TARGET_NAME)
        dev = await BleakScanner.find_device_by_name(P.TARGET_NAME, timeout=15.0)
        if not dev:
            log.warning("%s not found — is the phone still holding it?", P.TARGET_NAME)
            raise RuntimeError(f"{P.TARGET_NAME} not found — is the phone still holding it?")
        self._client = BleakClient(dev)
        await self._client.connect()
        log.info("connected to %s", P.TARGET_NAME)

    async def _write(self, payload: bytes, response: bool = False):
        """Write, transparently reconnecting on a stale connection (e.g. a
        hot-reload leaves is_connected=True but service discovery undone)."""
        try:
            await self._ensure()
            await self._client.write_gatt_char(P.CHAR_UUID, payload, response=response)
        except Exception as e:
            log.warning("write failed (%s) — resetting + reconnecting", e)
            await self._reset()
            await self._ensure()
            await self._client.write_gatt_char(P.CHAR_UUID, payload, response=response)

    async def send(self, payload: bytes, critical: bool = True):
        now = time.monotonic()
        # rate-limit non-critical traffic (brightness/colour/speed); drop the excess
        if not critical and self.max_rate and (now - self._last_send_t) < (1.0 / self.max_rate):
            self._dropped += 1
            return
        async with self._lock:
            await self._write(payload)
            self._count += 1
            self._last_send_t = time.monotonic()
            self._stamps.append(self._last_send_t)

    async def benchmark(self, n: int = 120):
        """Send n ACKNOWLEDGED writes (response=True) — each blocks until the strip
        confirms, so n/elapsed = the device's true sustained command rate."""
        async with self._lock:
            await self._ensure()
            payload = P.brightness(60)
            t0 = time.monotonic()
            for _ in range(n):
                await self._client.write_gatt_char(P.CHAR_UUID, payload, response=True)
            dt = time.monotonic() - t0
        result = {"n": n, "seconds": round(dt, 3), "rate": round(n / dt, 1),
                  "latency_ms": round(dt / n * 1000, 1)}
        log.info("benchmark: %s cmds in %ss = %s/s (%sms/cmd)",
                 n, result["seconds"], result["rate"], result["latency_ms"])
        return result

    async def disconnect(self):
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None

    # --- convenience wrappers (all critical = always delivered) ---
    async def power(self, on):       await self.send(P.power(on))
    async def color(self, r, g, b):  await self.send(P.color(r, g, b))
    async def brightness(self, pct): await self.send(P.brightness(pct))
    async def speed(self, pct):      await self.send(P.speed(pct))
    async def mode(self, m):         await self.send(P.mode(m))
    async def direction(self, fwd):  await self.send(P.direction(fwd))
