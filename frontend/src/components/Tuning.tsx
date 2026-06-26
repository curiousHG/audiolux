import { useState } from "react";
import { Info, Save, RotateCcw, Loader2, SlidersHorizontal } from "lucide-react";
import type { UseExplain } from "@/hooks/useExplain";
import { btnMini, cx } from "@/ui";

const GROUPS = ["Loudness → Brightness", "Spectrum → Colour", "Energy → Mood", "Tempo → Speed", "Build/Release → Direction"];

// Vertical, grouped algorithm sliders — sits next to the video.
export default function Tuning({ ex }: { ex: UseExplain }) {
  const { data, vals, busy, setVal, tune, loadConfig, saveConfig } = ex;
  const [name, setName] = useState("");
  if (!data) return null;
  const byGroup = (g: string) => Object.entries(data.params).filter(([, p]) => p.group === g);

  return (
    <div className="bg-panel border border-line rounded-xl p-3 flex flex-col gap-3 h-full">
      <div className="flex items-center gap-2">
        <SlidersHorizontal size={14} className="text-accent" />
        <span className="text-[11px] uppercase tracking-[1.2px] text-accent font-semibold">Tuning</span>
        {busy && <Loader2 size={13} className="animate-spin text-accent ml-auto" />}
      </div>

      {/* preset config bar */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <select onChange={(e) => loadConfig(e.target.value)} className="!w-auto !mb-0 !py-1 text-xs">
          {data.configs.map((c) => <option key={c}>{c}</option>)}
        </select>
        <RotateCcw size={13} className="text-dim cursor-pointer" aria-label="reset to Default" onClick={() => loadConfig("Default")} />
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="preset name"
               className="!w-[88px] px-2 py-1 text-xs rounded border border-line2 bg-panel text-ink" />
        <button className={cx(btnMini, "flex items-center gap-1")} onClick={() => { saveConfig(name); setName(""); }}><Save size={11} /> Save</button>
      </div>

      {/* groups spread across the available vertical space */}
      <div className="flex-1 flex flex-col justify-between gap-4 min-h-0">
        {GROUPS.map((g) => (
          <div key={g}>
            <div className="text-[11px] font-semibold text-[#c7ccd8] mb-2 pb-1 border-b border-line">{g}</div>
            <div className="flex flex-col gap-2.5">
              {byGroup(g).map(([k, p]) => (
                <div key={k} className="flex items-center gap-2">
                  <span className="text-[11px] text-mute w-[108px] shrink-0 flex items-center gap-1">
                    {p.label}
                    <span title={p.desc} className="inline-flex cursor-help"><Info size={11} className="text-dim shrink-0" /></span>
                  </span>
                  <input type="range" min={p.min} max={p.max} step={p.step} value={vals[k] ?? p.value}
                         onChange={(e) => setVal(k, +e.target.value)} onMouseUp={() => tune(k)} onTouchEnd={() => tune(k)} className="flex-1" />
                  <span className="text-[11px] text-accent w-[38px] text-right tabular-nums">{vals[k] ?? p.value}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="text-[10px] text-dim">Analysis sliders re-run analysis on release; speed applies instantly.</div>
    </div>
  );
}
