import { useEffect, useRef } from "react";
import type { Telemetry as T } from "@/api";
import { card2, ro, note } from "@/ui";

const roSpan = "block text-[10px] text-mute uppercase tracking-[.5px]";
const tlabel = "text-xs text-[#c7ccd8] font-medium mb-1.5";
const canvasCls = "w-full h-[11vh] min-h-[56px] bg-panel2 rounded-lg block";

const fmtHz = (f: number) => (f >= 1000 ? `${+(f / 1000).toFixed(f < 10000 ? 1 : 0)}k` : `${Math.round(f)}`);
const fmtAmp = (a: number) => (a < 1e-3 ? "0" : a < 10 ? a.toFixed(a < 1 ? 2 : 1) : `${Math.round(a)}`);

export interface HistPoint { level: number; bright: number; color: string; centroid: number }

interface Props {
  telem: T | null;
  hist: HistPoint[];
  colorHex: Record<string, string>;
  barColors: string[];
  barFreqs: number[];
  num2name: Record<number, string>;
  hasTrack?: boolean;          // a song is loaded -> the full-width timeline is shown elsewhere
}

function fit(c: HTMLCanvasElement): [CanvasRenderingContext2D, number, number] {
  const W = (c.width = c.clientWidth), H = (c.height = c.clientHeight);
  return [c.getContext("2d")!, W, H];
}

// Spectrum as HORIZONTAL bars: frequency on the Y axis (low at the bottom), bar
// length = amplitude on the X axis. The amplitude axis AUTO-RANGES to `vmax` (a
// rolling peak), so the full signal is shown and the scale grows/shrinks with it.
// Labelled with real band centre frequencies and real amplitude values.
function drawSpectrum(c: HTMLCanvasElement, vals: number[], colors: string[], freqs: number[], vmax: number) {
  const [x, W, H] = fit(c);
  x.clearRect(0, 0, W, H);
  const n = vals.length; if (!n) return;
  const padL = 50, padR = 8, padT = 6, padB = 26;
  const plotW = Math.max(1, W - padL - padR), plotH = Math.max(1, H - padT - padB);
  const x0 = padL, y0 = padT, yB = y0 + plotH;
  const bh = plotH / n;
  const sc = vmax > 1e-6 ? 1 / vmax : 1;          // plot-width fraction per unit amplitude

  // amplitude gridlines (half + full scale)
  x.strokeStyle = "#222838"; x.lineWidth = 1;
  [0.5, 1].forEach((f) => { const X = x0 + f * plotW; x.beginPath(); x.moveTo(X, y0); x.lineTo(X, yB); x.stroke(); });

  // bars — index 0 (low freq) at the bottom, growing rightwards by amplitude/vmax
  for (let i = 0; i < n; i++) {
    const len = Math.min(1, Math.max(0, vals[i]) * sc) * plotW;
    const y = yB - (i + 1) * bh;
    x.fillStyle = colors[i] || "#5b8cff";
    x.fillRect(x0, y + 0.4, Math.max(1, len), Math.max(1, bh - 0.6));
  }

  // axis lines
  x.strokeStyle = "#3a4254"; x.lineWidth = 1;
  x.beginPath(); x.moveTo(x0, y0); x.lineTo(x0, yB); x.lineTo(x0 + plotW, yB); x.stroke();

  x.fillStyle = "#7c8597"; x.font = "9px ui-monospace, SFMono-Regular, monospace";

  // amplitude axis labels (X) — real values at 0, half-scale, full-scale
  x.textAlign = "center"; x.textBaseline = "top";
  ([0, 0.5, 1] as const).forEach((f) => x.fillText(fmtAmp(f * vmax), x0 + f * plotW, yB + 4));
  x.fillText("amplitude", x0 + plotW / 2, yB + 15);

  // frequency axis labels (Y) — real band centre frequencies
  if (freqs.length === n) {
    x.textAlign = "right"; x.textBaseline = "middle";
    const ticks = 7;
    for (let k = 0; k < ticks; k++) {
      const i = Math.round((k / (ticks - 1)) * (n - 1));
      const y = yB - (i + 0.5) * bh;
      x.fillText(fmtHz(freqs[i]), x0 - 5, y);
      x.strokeStyle = "#3a4254"; x.beginPath(); x.moveTo(x0 - 3, y); x.lineTo(x0, y); x.stroke();
    }
    x.textAlign = "left"; x.textBaseline = "top";
    x.fillText("Hz", 2, yB + 15);
  }
}

function lineSeries(x: CanvasRenderingContext2D, hist: HistPoint[], key: keyof HistPoint, col: string, W: number, H: number) {
  x.strokeStyle = col; x.lineWidth = 1.6; x.beginPath();
  const n = hist.length;
  for (let i = 0; i < n; i++) {
    const X = n < 2 ? 0 : (i / (n - 1)) * W, Y = H - (hist[i][key] as number) * (H - 3) - 1.5;
    i ? x.lineTo(X, Y) : x.moveTo(X, Y);
  }
  x.stroke();
}

export default function Telemetry({ telem, hist, colorHex, barColors, barFreqs, num2name, hasTrack }: Props) {
  const spec = useRef<HTMLCanvasElement>(null);
  const lb = useRef<HTMLCanvasElement>(null);
  const col = useRef<HTMLCanvasElement>(null);
  const peak = useRef(1);                          // rolling amplitude peak -> auto-ranged axis

  // spectrum bars come from the backend (precomputed timeline for tracks, live
  // analysis for the mic). The amplitude axis auto-ranges: it jumps up to the
  // loudest bar instantly and decays slowly, so the scale tracks the real signal.
  useEffect(() => {
    if (!spec.current || !telem?.spectrum) return;
    const vals = telem.spectrum;
    const fmax = vals.length ? Math.max(...vals) : 0;
    peak.current = Math.max(fmax, peak.current * 0.94, 0.25);   // attack now, ~1 s release, floor 0.25
    drawSpectrum(spec.current, vals, barColors, barFreqs, peak.current);
  }, [telem, barColors, barFreqs]);

  // loudness -> brightness, and frequency -> colour, both from history
  useEffect(() => {
    if (lb.current) {
      const [x, W, H] = fit(lb.current);
      x.clearRect(0, 0, W, H);
      x.fillStyle = "#5ad28a22"; x.beginPath(); x.moveTo(0, H);
      hist.forEach((p, i) => { const X = hist.length < 2 ? 0 : (i / (hist.length - 1)) * W; x.lineTo(X, H - p.bright * (H - 3) - 1.5); });
      x.lineTo(W, H); x.closePath(); x.fill();
      lineSeries(x, hist, "level", "#7fd0ff", W, H);
      lineSeries(x, hist, "bright", "#5ad28a", W, H);
    }
    if (col.current) {
      const [x, W, H] = fit(col.current);
      x.clearRect(0, 0, W, H);
      const n = hist.length;
      if (n) {
        const bw = W / n;
        hist.forEach((p, i) => { x.fillStyle = colorHex[p.color] || "#333"; x.fillRect((i / n) * W, 0, Math.ceil(bw) + 1, H); });
        x.strokeStyle = "#ffffffcc"; x.lineWidth = 1.4; x.beginPath();
        hist.forEach((p, i) => { const X = n < 2 ? 0 : (i / (n - 1)) * W, Y = H - p.centroid * (H - 3) - 1.5; i ? x.lineTo(X, Y) : x.moveTo(X, Y); });
        x.stroke();
      }
    }
  }, [telem, hist, colorHex]);

  const t = telem;
  const beatOn = (t?.beat_flash || 0) > 0.2;
  const dot = "inline-block w-3 h-3 rounded-full align-[-1px] mr-[5px]";
  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex flex-wrap gap-1.5 mb-2 shrink-0">
        <div className={ro}><span className={roSpan}>BPM</span><b className="text-sm tabular-nums">{t && t.bpm > 0 ? t.bpm : "—"}</b></div>
        <div className={ro}><span className={roSpan}>Beat</span><b><i className="inline-block w-3 h-3 rounded-full transition-transform" style={{ background: beatOn ? "#57d090" : "#2a3142", transform: `scale(${1 + (t?.beat_flash || 0) * 0.6})` }} /></b></div>
        {t?.C != null && <div className={ro}><span className={roSpan}>C</span><b className="text-sm tabular-nums">{t.C}</b></div>}
        {t?.mood != null && <div className={ro}><span className={roSpan}>Mood</span><b className="text-sm">{t.mood}</b></div>}
        <div className={ro}><span className={roSpan}>Colour</span><b className="text-sm"><i className={dot} style={{ background: colorHex[t?.color || ""] || "#2a3142" }} />{t?.color || "—"}</b></div>
        <div className={ro}><span className={roSpan}>Family</span><b className="text-xs">{t?.family || "—"}</b></div>
        <div className={ro}><span className={roSpan}>Effect</span><b className="text-xs">{t?.mode ? (num2name[t.mode] || "#" + t.mode) : "—"}</b></div>
        <div className={ro}><span className={roSpan}>Dir</span><b className="text-sm">{t?.direction === "bwd" ? "◀" : "▶"}</b></div>
      </div>

      {!hasTrack && (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-2 mb-2 shrink-0">
          <div className={card2}>
            <div className={tlabel + " !mb-1"}>Loudness → Brightness</div>
            <canvas ref={lb} className={canvasCls} />
          </div>
          <div className={card2}>
            <div className={tlabel + " !mb-1"}>Frequency → Colour</div>
            <canvas ref={col} className={canvasCls} />
          </div>
        </div>
      )}

      {/* spectrum sticks to the bottom of the column and fills the leftover height */}
      <div className={card2 + " flex flex-col flex-1 min-h-0 mt-auto"}>
        <div className={tlabel + " flex items-center justify-between !mb-1 shrink-0"}>
          <span>Spectrum <span className={note}>(live · whitened)</span></span>
          <span className="flex items-center gap-1.5 text-[11px] text-mute">suggests
            <i className="inline-block w-3 h-3 rounded-full" style={{ background: colorHex[t?.color || ""] || "#2a3142" }} />
            <b className="text-ink">{t?.color || "—"}</b>
          </span>
        </div>
        <canvas ref={spec} className="w-full flex-1 min-h-[200px] bg-panel2 rounded-lg block" />
      </div>
    </div>
  );
}
