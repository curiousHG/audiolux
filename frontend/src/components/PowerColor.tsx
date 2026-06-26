import { useEffect, useRef } from "react";

const SWATCHES = ["#ff0000", "#ff7a00", "#ffd400", "#33ff00", "#00ffd0", "#0066ff", "#a000ff", "#ffffff"];

function hsv2rgb(h: number, s: number, v: number): [number, number, number] {
  const c = v * s, x = c * (1 - Math.abs(((h / 60) % 2) - 1)), m = v - c;
  let r = 0, g = 0, b = 0;
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
}
const hx = (n: number) => n.toString(16).padStart(2, "0");

export default function PowerColor({ act }: { act: (u: string) => void }) {
  const wheel = useRef<HTMLCanvasElement>(null);
  const marker = useRef<HTMLDivElement>(null);
  const colInput = useRef<HTMLInputElement>(null);

  function setColor(hex: string) {
    if (colInput.current) colInput.current.value = "#" + hex;
    act("/api/color?hex=" + hex);
  }

  useEffect(() => {
    const cv = wheel.current!, ctx = cv.getContext("2d")!, SZ = 200, R = SZ / 2;
    cv.width = SZ; cv.height = SZ;
    const img = ctx.createImageData(SZ, SZ);
    for (let y = 0; y < SZ; y++)
      for (let x = 0; x < SZ; x++) {
        const dx = x - R, dy = y - R, d = Math.hypot(dx, dy), i = (y * SZ + x) * 4;
        if (d > R) { img.data[i + 3] = 0; continue; }
        let h = (Math.atan2(dy, dx) * 180) / Math.PI; if (h < 0) h += 360;
        const [r, g, b] = hsv2rgb(h, Math.min(1, d / R), 1);
        img.data[i] = r; img.data[i + 1] = g; img.data[i + 2] = b; img.data[i + 3] = 255;
      }
    ctx.putImageData(img, 0, 0);

    let drag = false, last = 0, pend: string | null = null;
    const flush = () => { if (pend) { act("/api/color?hex=" + pend); pend = null; } };
    function pick(e: PointerEvent) {
      const rc = cv.getBoundingClientRect();
      let x = e.clientX - rc.left, y = e.clientY - rc.top, dx = x - R, dy = y - R, d = Math.hypot(dx, dy);
      if (d > R) { dx *= R / d; dy *= R / d; x = R + dx; y = R + dy; d = R; }
      let h = (Math.atan2(dy, dx) * 180) / Math.PI; if (h < 0) h += 360;
      const [r, g, b] = hsv2rgb(h, Math.min(1, d / R), 1), hex = hx(r) + hx(g) + hx(b);
      if (marker.current) { marker.current.style.left = x + "px"; marker.current.style.top = y + "px"; }
      if (colInput.current) colInput.current.value = "#" + hex;
      pend = hex;
      const now = performance.now();
      if (now - last > 80) { last = now; flush(); }
    }
    const down = (e: PointerEvent) => { drag = true; cv.setPointerCapture(e.pointerId); pick(e); };
    const move = (e: PointerEvent) => { if (drag) pick(e); };
    const up = () => { drag = false; flush(); };
    cv.addEventListener("pointerdown", down);
    cv.addEventListener("pointermove", move);
    cv.addEventListener("pointerup", up);
    return () => { cv.removeEventListener("pointerdown", down); cv.removeEventListener("pointermove", move); cv.removeEventListener("pointerup", up); };
  }, [act]);

  return (
    <section className="col">
      <h2>Power &amp; Color</h2>
      <div className="row" style={{ marginTop: 0 }}>
        <button className="on" onClick={() => act("/api/power?on=1")}>ON</button>
        <button className="off" onClick={() => act("/api/power?on=0")}>OFF</button>
      </div>
      <div className="wheelwrap">
        <canvas ref={wheel} id="wheel" />
        <div ref={marker} id="marker" />
      </div>
      <input ref={colInput} type="color" defaultValue="#ff0000"
             onInput={(e) => setColor((e.target as HTMLInputElement).value.replace("#", ""))} />
      <div className="swatches">
        {SWATCHES.map((c) => (
          <div key={c} className="sw" style={{ background: c }} onClick={() => setColor(c.replace("#", ""))} />
        ))}
      </div>
    </section>
  );
}
