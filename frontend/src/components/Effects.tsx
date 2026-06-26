import { useMemo, useState } from "react";
import type { ModeGroup, EffectMode } from "../api";

function modeNum(e: EffectMode, forward: boolean): number {
  if ("single" in e) return e.single!;
  if ("open" in e || "close" in e) return (forward ? (e.open ?? e.close) : (e.close ?? e.open))!;
  return (forward ? (e.fwd ?? e.bwd) : (e.bwd ?? e.fwd))!;
}

export default function Effects({ act, groups }: { act: (u: string) => void; groups: ModeGroup[] }) {
  const effects = useMemo(() => groups.flatMap((g) => g.effects), [groups]);
  const [sel, setSel] = useState(0);
  const [fwd, setFwd] = useState(true);
  const [md, setMd] = useState("95");
  const [bright, setBright] = useState(60);
  const [speed, setSpeed] = useState(50);

  const cur = effects[sel];
  const oc = cur ? "open" in cur || "close" in cur : false;
  const single = cur ? "single" in cur : false;

  function apply(i: number, forward: boolean, silent = false) {
    const e = effects[i];
    if (!e) return;
    const n = modeNum(e, forward);
    setMd(String(n));
    if (!silent) act("/api/mode?m=" + n);
  }
  function chooseMode(i: number) { setSel(i); apply(i, fwd); }
  function setDir(f: boolean) { setFwd(f); apply(sel, f); }
  function go(n: number) {
    const v = Math.max(1, Math.min(255, n || 1));
    setMd(String(v));
    for (let i = 0; i < effects.length; i++) {
      const e = effects[i];
      if (e.single === v || e.fwd === v || e.open === v) { setSel(i); setFwd(true); return act("/api/mode?m=" + v); }
      if (e.bwd === v || e.close === v) { setSel(i); setFwd(false); return act("/api/mode?m=" + v); }
    }
    act("/api/mode?m=" + v);
  }

  let flat = 0;
  return (
    <section className="col">
      <h2>Adjust &amp; Effects</h2>
      <label>Brightness <span className="val">{bright}</span></label>
      <input type="range" min={1} max={100} value={bright}
             onChange={(e) => setBright(+e.target.value)}
             onMouseUp={() => act("/api/bright?v=" + bright)}
             onTouchEnd={() => act("/api/bright?v=" + bright)} />
      <label>Speed <span className="val">{speed}</span></label>
      <input type="range" min={1} max={100} value={speed}
             onChange={(e) => setSpeed(+e.target.value)}
             onMouseUp={() => act("/api/speed?v=" + speed)}
             onTouchEnd={() => act("/api/speed?v=" + speed)} />

      <label>Effect (grouped by family)</label>
      <select value={sel} onChange={(e) => chooseMode(+e.target.value)}>
        {groups.map((g) => (
          <optgroup key={g.family} label={g.family}>
            {g.effects.map((e) => {
              const i = flat++;
              return <option key={i} value={i}>{e.name}</option>;
            })}
          </optgroup>
        ))}
      </select>

      <label>Direction <span className="val">#{md}</span></label>
      <div className="row" style={{ marginTop: 0 }}>
        <button className={fwd ? "on" : ""} disabled={single} onClick={() => setDir(true)}>
          {oc ? "⤢ Open" : "⟶ Forward"}
        </button>
        <button className={!fwd ? "on" : ""} disabled={single} onClick={() => setDir(false)}>
          {oc ? "⤡ Close" : "⟵ Backward"}
        </button>
      </div>
      <div className="mode" style={{ marginTop: 12 }}>
        <button onClick={() => go((parseInt(md) || 1) - 1)}>‹ Prev</button>
        <input type="number" min={1} max={255} value={md} onChange={(e) => setMd(e.target.value)} />
        <button onClick={() => go((parseInt(md) || 1) + 1)}>Next ›</button>
        <button style={{ flex: 0.7 }} onClick={() => go(parseInt(md) || 1)}>Go</button>
      </div>
    </section>
  );
}
