import { useEffect, useRef, useState } from "react";
import type { CmdStats } from "../api";
import { get } from "../api";
import { btnMini, val } from "../ui";

export default function CommandRate({ cmds }: { cmds: CmdStats | null }) {
  const cg = useRef<HTMLCanvasElement>(null);
  const [bench, setBench] = useState("");

  useEffect(() => {
    const c = cg.current; if (!c || !cmds) return;
    const W = (c.width = c.clientWidth), H = (c.height = c.clientHeight), x = c.getContext("2d")!;
    x.clearRect(0, 0, W, H);
    const h = cmds.hist || [], n = h.length; if (!n) return;
    const bucket = cmds.bucket || 0.5;
    const ps = h.map((v) => v / bucket);
    const mx = Math.max(cmds.max_rate * 1.3, 8, ...ps), bw = W / n;
    for (let i = 0; i < n; i++) {
      const v = ps[i] / mx, bh = v * (H - 4);
      x.fillStyle = `hsl(${140 - v * 140},70%,55%)`;
      x.fillRect(i * bw, H - bh, Math.max(1, bw - 1), bh);
    }
    const yl = H - (cmds.max_rate / mx) * (H - 4);
    x.strokeStyle = "#ff6b8188"; x.setLineDash([4, 4]);
    x.beginPath(); x.moveTo(0, yl); x.lineTo(W, yl); x.stroke(); x.setLineDash([]);
    x.fillStyle = "#ff6b81aa"; x.font = "10px system-ui";
    x.fillText(`limit ${cmds.max_rate}/s`, 4, Math.max(10, yl - 3));
  }, [cmds]);

  async function benchmark() {
    setBench("measuring…");
    const j = await get<any>("/api/benchmark?n=80");
    if (!j.ok) { setBench("✗ " + j.error); return; }
    const safe = Math.max(5, Math.floor(j.rate) - 1);
    await get("/api/maxrate?r=" + safe);
    setBench(`strip max ≈ ${j.rate}/s (${j.latency_ms}ms/cmd) → limiter set to ${safe}/s`);
  }

  return (
    <div className="mt-[22px] pt-[14px] border-t border-line">
      <label className="block text-xs text-mute mb-1.5">
        Commands sent to strip <span className={val}>{cmds?.rate ?? 0} /s</span>
        <span className="text-dim"> {cmds ? `${cmds.total} total · ${cmds.dropped} dropped` : ""}</span>
        <button className={btnMini + " float-right"} onClick={benchmark}>Benchmark strip max-rate</button>
        <span className="text-dim float-right mr-2">{bench}</span>
      </label>
      <canvas ref={cg} className="w-full h-[72px] bg-panel2 border border-line rounded-[10px] mt-1" />
    </div>
  );
}
