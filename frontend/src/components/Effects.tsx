import { useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, ChevronLeft, ChevronRight, ChevronsLeftRight, ChevronsRightLeft } from "lucide-react";
import type { ModeGroup, EffectMode } from "@/api";
import { h2, row, btn, label, val, cx } from "@/ui";

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
  // Find the effect (and direction) that owns a given mode number; keeps the
  // dropdown + direction toggle in sync with whatever number is shown.
  function syncTo(v: number): boolean {
    for (let i = 0; i < effects.length; i++) {
      const e = effects[i];
      if (e.single === v || e.fwd === v || e.open === v) { setSel(i); setFwd(true); return true; }
      if (e.bwd === v || e.close === v) { setSel(i); setFwd(false); return true; }
    }
    return false;
  }
  // Typing/stepping the number box: reflect it in the dropdown immediately (no send).
  function onNum(s: string) {
    setMd(s);
    const v = parseInt(s);
    if (Number.isFinite(v)) syncTo(v);
  }
  function go(n: number) {
    const v = Math.max(1, Math.min(255, n || 1));
    setMd(String(v));
    syncTo(v);
    act("/api/mode?m=" + v);
  }

  let flat = 0;
  return (
    <section className="min-w-0">
      <h2 className={h2}>Adjust &amp; Effects</h2>
      <label className={label}>Brightness <span className={val}>{bright}</span></label>
      <input type="range" min={1} max={100} value={bright}
             onChange={(e) => setBright(+e.target.value)}
             onMouseUp={() => act("/api/bright?v=" + bright)}
             onTouchEnd={() => act("/api/bright?v=" + bright)} />
      <label className={label}>Speed <span className={val}>{speed}</span></label>
      <input type="range" min={1} max={100} value={speed}
             onChange={(e) => setSpeed(+e.target.value)}
             onMouseUp={() => act("/api/speed?v=" + speed)}
             onTouchEnd={() => act("/api/speed?v=" + speed)} />

      <label className={label}>Effect (grouped by family)</label>
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

      <label className={label}>Direction <span className={val}>#{md}</span></label>
      <div className={cx(row, "mt-0")}>
        <button className={cx(btn, "flex items-center justify-center", fwd && "!bg-on")} disabled={single} title={oc ? "Open" : "Forward"} onClick={() => setDir(true)}>
          {oc ? <ChevronsLeftRight size={18} /> : <ArrowRight size={18} />}
        </button>
        <button className={cx(btn, "flex items-center justify-center", !fwd && "!bg-on")} disabled={single} title={oc ? "Close" : "Backward"} onClick={() => setDir(false)}>
          {oc ? <ChevronsRightLeft size={18} /> : <ArrowLeft size={18} />}
        </button>
      </div>
      <div className="flex gap-2 items-center mt-3">
        <button className={cx(btn, "flex items-center justify-center gap-0.5")} title="Previous mode" onClick={() => go((parseInt(md) || 1) - 1)}><ChevronLeft size={16} /> Prev</button>
        <input className="flex-1 text-center" type="number" min={1} max={255} value={md}
               onChange={(e) => onNum(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && go(parseInt(md) || 1)} />
        <button className={cx(btn, "flex items-center justify-center gap-0.5")} title="Next mode" onClick={() => go((parseInt(md) || 1) + 1)}>Next <ChevronRight size={16} /></button>
        <button className={cx(btn, "!flex-[0.7]")} onClick={() => go(parseInt(md) || 1)}>Go</button>
      </div>
    </section>
  );
}
