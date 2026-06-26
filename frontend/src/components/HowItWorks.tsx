import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Info, Save, RotateCcw, Loader2 } from "lucide-react";
import { get } from "@/api";
import { btnMini, cx } from "@/ui";

interface Param { value: number; min: number; max: number; step: number; reanalyse: boolean; group: string; label: string; desc: string; }
interface Explain {
  params: Record<string, Param>;
  mood_names: string[];
  mood_families: Record<string, string[]>;
  freq_colors: string[];
  color_hex: Record<string, string>;
  speed: { lo: number; span: number; min: number; max: number };
  dsp: { sr: number; n_fft: number; hop: number; nbars: number; fps: number };
  configs: string[];
}

// how each FEATURE is computed from the audio (grounded in analysis.analyze)
function features(dsp: Explain["dsp"]): [string, string, string][] {
  return [
    ["STFT", `librosa.stft(y, n_fft=${dsp.n_fft}, hop=${dsp.hop}) @ ${dsp.sr} Hz`, `magnitude spectrogram S — the basis for everything, ~${dsp.fps} frames/s`],
    ["Loudness", "librosa.feature.rms(S)", "per-frame RMS → dB vs the song's 95th-pct level"],
    ["Spectrum", `${dsp.nbars} log bars 30 Hz–16 kHz (mean |S|), ÷ each bar's song-average`, "whitened bars → 6 colour groups"],
    ["Percussiveness", "librosa.decompose.hpss(S)", "harmonic/percussive split → p = ΣP / (ΣH + ΣP)"],
    ["Beats & tempo", "onset_strength → beat_track / feature.tempo(aggregate=None)", "beat grid + global BPM + local BPM curve (octave-folded)"],
    ["Spectral centroid", "librosa.feature.spectral_centroid(S)", "the 'brightness' of the timbre (telemetry line)"],
    ["Build/release", "slow EMA of brightness (α = 0.02)", "brightness vs its slow average → direction"],
  ];
}

const GROUPS = ["Loudness → Brightness", "Spectrum → Colour", "Energy → Mood", "Tempo → Speed", "Build/Release → Direction"];
const FILES: Record<string, string> = {
  "Loudness → Brightness": "analysis.analyze · player.tick",
  "Spectrum → Colour": "analysis._color_track",
  "Energy → Mood": "analysis._mood_track · modes.mood_family",
  "Tempo → Speed": "analysis (beat_track / tempo) · player.tick",
  "Build/Release → Direction": "analysis._direction_track",
};
const fx = "font-mono text-[11px] bg-panel2 rounded px-1.5 py-0.5 text-[#c7ccd8]";

// the actual formula for each group, grounded in the live param values
function Formula({ group, v, d }: { group: string; v: Record<string, number>; d: Explain }) {
  if (group === "Loudness → Brightness") return (
    <p className="text-xs text-mute leading-relaxed">
      Loudness is the FFT's RMS in dB vs the song's 95th-pct level. Then{" "}
      <code className={fx}>bright = clip((dB − ({v.db_floor})) / {(-v.db_floor).toFixed(0)}, 0, 1)</code>, and the strip gets{" "}
      <code className={fx}>floor + bright·(100 − floor)</code> %.
    </p>
  );
  if (group === "Spectrum → Colour") return (
    <p className="text-xs text-mute leading-relaxed">
      Each of 40 log bars is whitened (÷ its own song-average) and shown as <code className={fx}>(bar·0.5)^{v.spec_gamma}</code>.
      The 6 colour groups <b>{d.freq_colors.join(" ")}</b> (bass→treble) are summed with the top band ×<code className={fx}>{v.white_deemph}</code>;
      the loudest group is the colour. Below <code className={fx}>{v.colour_silence}</code> brightness it holds. (Colour = the tallest visible bars.)
    </p>
  );
  if (group === "Energy → Mood") return (
    <div className="text-xs text-mute leading-relaxed">
      From loudness <i>e</i> + percussive fraction <i>p</i> (HPSS):{" "}
      <code className={fx}>peak</code> if e&gt;{v.mood_peak_e} &amp; p&gt;{v.mood_peak_p} ·{" "}
      <code className={fx}>drive</code> if e&gt;{v.mood_drive_e} · <code className={fx}>groove</code> if e&gt;{v.mood_groove_e} · else <code className={fx}>calm</code>.
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5">
        {d.mood_names.map((m, i) => (
          <span key={m}><b className="text-ink capitalize">{m}</b> → {(d.mood_families[String(i)] || []).slice(0, 3).join(", ")}</span>
        ))}
      </div>
      <span className="text-dim">peak ⇒ coloured strobe · others ⇒ the family that can show the colour, → mode via resolve_mode.</span>
    </div>
  );
  if (group === "Tempo → Speed") return (
    <p className="text-xs text-mute leading-relaxed">
      Beats come from beat-tracking; the family switches every N beats (Mic-engine slider). Animation speed tracks the local BPM:{" "}
      <code className={fx}>clip({d.speed.lo} + (BPM − {v.speed_bpm_lo})/{v.speed_span}·{d.speed.span}, {d.speed.min}, {d.speed.max})</code>.
    </p>
  );
  return (
    <p className="text-xs text-mute leading-relaxed">
      <code className={fx}>slow</code> = slow EMA of brightness. Forward when <code className={fx}>bright &gt; slow·{v.dir_build}</code>,
      backward when <code className={fx}>bright &lt; slow·{v.dir_release}</code>, else hold.
    </p>
  );
}

function DiagramBox({ title, lines }: { title: string; lines?: string[] }) {
  return (
    <div className="flex-1 min-w-0 bg-panel2 border border-line rounded-lg px-2.5 py-2 text-center">
      <div className="text-[11px] font-semibold text-accent">{title}</div>
      {lines && <div className="text-[10px] text-mute mt-1 leading-snug">{lines.map((l) => <div key={l}>{l}</div>)}</div>}
    </div>
  );
}

export default function HowItWorks({ act, onPlanChange }: { act: (u: string) => void; onPlanChange: () => void }) {
  const [open, setOpen] = useState(false);
  const [d, setD] = useState<Explain | null>(null);
  const [v, setV] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [sel, setSel] = useState("Default");

  const refresh = async () => {
    const j = await get<Explain & { ok: boolean }>("/api/explain");
    setD(j);
    setV(Object.fromEntries(Object.entries(j.params).map(([k, p]) => [k, p.value])));
  };
  useEffect(() => { if (open && !d) refresh(); }, [open]);   // eslint-disable-line react-hooks/exhaustive-deps

  async function tune(key: string, value: number) {
    const p = d!.params[key];
    if (p.reanalyse) setBusy(true);
    await get(`/api/tune?name=${key}&value=${value}`);
    if (p.reanalyse) { setBusy(false); onPlanChange(); }
  }
  async function loadCfg(n: string) {
    setBusy(true);
    await get("/api/config/load?name=" + encodeURIComponent(n));
    setBusy(false);
    await refresh(); onPlanChange();
    act("/api/state");   // nudge a status line
  }
  async function saveCfg() {
    if (!name.trim()) return;
    const j = await get<{ configs: string[] }>("/api/config/save?name=" + encodeURIComponent(name.trim()));
    setD((p) => p ? { ...p, configs: j.configs } : p); setSel(name.trim()); setName("");
  }

  const byGroup = (g: string) => d ? Object.entries(d.params).filter(([, p]) => p.group === g) : [];

  return (
    <div className="mt-3 bg-panel border border-line rounded-xl">
      <button onClick={() => setOpen((o) => !o)} className="w-full flex items-center gap-2 px-4 py-3 text-left cursor-pointer">
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <span className="text-[13px] font-semibold">How it works</span>
        <span className="text-[11px] text-dim">— what drives each light parameter, the maths, and live tuning</span>
        {busy && <Loader2 size={14} className="ml-auto animate-spin text-accent" />}
      </button>

      {open && d && (
        <div className="px-4 pb-4 flex flex-col gap-4">
          {/* flow diagram */}
          <div className="flex items-center gap-1.5">
            <DiagramBox title="🎵 Audio → FFT" />
            <ChevronRight size={16} className="text-dim shrink-0" />
            <DiagramBox title="Features" lines={["RMS loudness", "whitened spectrum", "HPSS percussive", "onset / beats"]} />
            <ChevronRight size={16} className="text-dim shrink-0" />
            <DiagramBox title="Decisions" lines={["→ brightness", "→ colour", "→ mood → family", "→ speed", "→ direction"]} />
            <ChevronRight size={16} className="text-dim shrink-0" />
            <DiagramBox title="🎚 mode" lines={["family + colour", "→ mode #", "→ 💡 strip"]} />
          </div>

          {/* features — how they're computed */}
          <div className="bg-panel2 border border-line rounded-lg p-3">
            <div className="text-xs font-semibold text-[#c7ccd8] mb-2">
              Features <span className="text-mute font-normal">— how they're computed from the audio</span>
              <span className="text-[10px] text-dim font-mono ml-2">analysis.analyze</span>
            </div>
            <div className="grid md:grid-cols-2 gap-x-6 gap-y-2">
              {features(d.dsp).map(([fname, code, desc]) => (
                <div key={fname} className="text-xs">
                  <span className="text-ink font-medium">{fname}</span>
                  <code className={cx(fx, "ml-1.5")}>{code}</code>
                  <div className="text-mute mt-0.5">{desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* config bar */}
          <div className="flex items-center gap-2 flex-wrap bg-panel2 border border-line rounded-lg px-3 py-2">
            <span className="text-xs text-mute">Config</span>
            <select value={sel} onChange={(e) => { setSel(e.target.value); loadCfg(e.target.value); }} className="!w-auto !mb-0 !py-1.5 text-xs">
              {(d.configs || ["Default"]).map((c) => <option key={c}>{c}</option>)}
            </select>
            <RotateCcw size={13} className="text-dim cursor-pointer" onClick={() => loadCfg("Default")} />
            <span className="text-dim text-xs ml-2">save current as</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="my preset"
                   className="!w-[120px] px-2 py-1 text-xs rounded border border-line2 bg-panel text-ink" />
            <button className={cx(btnMini, "flex items-center gap-1")} onClick={saveCfg}><Save size={12} /> Save</button>
            {busy && <span className="text-[11px] text-accent flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> re-analysing…</span>}
          </div>

          {/* per-group explanation + sliders */}
          <div className="grid md:grid-cols-2 gap-3">
            {GROUPS.map((g) => (
              <div key={g} className="bg-panel2 border border-line rounded-lg p-3">
                <div className="flex items-baseline justify-between mb-1.5">
                  <span className="text-xs font-semibold text-[#c7ccd8]">{g}</span>
                  <span className="text-[10px] text-dim font-mono">{FILES[g]}</span>
                </div>
                <Formula group={g} v={v} d={d} />
                <div className="mt-2.5 flex flex-col gap-1.5">
                  {byGroup(g).map(([k, p]) => (
                    <div key={k} className="flex items-center gap-2">
                      <span className="text-[11px] text-mute w-[120px] shrink-0 flex items-center gap-1">
                        {p.label}
                        <span title={p.desc} className="inline-flex cursor-help"><Info size={11} className="text-dim shrink-0" /></span>
                      </span>
                      <input type="range" min={p.min} max={p.max} step={p.step} value={v[k] ?? p.value}
                             onChange={(e) => setV((s) => ({ ...s, [k]: +e.target.value }))}
                             onMouseUp={() => tune(k, v[k])} onTouchEnd={() => tune(k, v[k])} className="flex-1" />
                      <span className="text-[11px] text-accent w-[40px] text-right tabular-nums">{v[k] ?? p.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="text-[11px] text-dim">Analysis sliders re-run the offline analysis on the loaded track when you release them; speed sliders apply instantly.</div>
        </div>
      )}
    </div>
  );
}
