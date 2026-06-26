import { useEffect, useRef } from "react";
import type { Telemetry as T } from "@/api";
import { h2, card2, ro, note } from "@/ui";

const roSpan = "block text-[10px] text-mute uppercase tracking-[.5px]";
const tlabel = "text-xs text-[#c7ccd8] font-medium mb-1.5";
const canvasCls = "w-full h-[150px] bg-panel2 rounded-lg";

export interface HistPoint { level: number; bright: number; color: string; centroid: number }

interface Props {
  telem: T | null;
  hist: HistPoint[];
  colorHex: Record<string, string>;
  barColors: string[];
  num2name: Record<number, string>;
  hasTrack?: boolean;          // a song is loaded -> the full-width timeline is shown elsewhere
}

function fit(c: HTMLCanvasElement): [CanvasRenderingContext2D, number, number] {
  const W = (c.width = c.clientWidth), H = (c.height = c.clientHeight);
  return [c.getContext("2d")!, W, H];
}

function drawBars(c: HTMLCanvasElement, vals: number[], colors: string[]) {
  const [x, W, H] = fit(c);
  x.clearRect(0, 0, W, H);
  const n = vals.length; if (!n) return;
  const bw = W / n;
  for (let i = 0; i < n; i++) {
    const h = Math.max(0, Math.min(1, vals[i])) * (H - 2);
    x.fillStyle = colors[i] || "#5b8cff";
    x.fillRect(i * bw, H - h, Math.max(1, bw - 1), h);
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

export default function Telemetry({ telem, hist, colorHex, barColors, num2name, hasTrack }: Props) {
  const spec = useRef<HTMLCanvasElement>(null);
  const sugg = useRef<HTMLCanvasElement>(null);
  const lb = useRef<HTMLCanvasElement>(null);
  const col = useRef<HTMLCanvasElement>(null);

  // spectrum bars come from the backend (precomputed timeline for tracks, live
  // analysis for the mic) — consistent scaling + colours either way
  useEffect(() => {
    if (spec.current && telem?.spectrum) drawBars(spec.current, telem.spectrum, barColors);
    // suggested-colour strip: the colour the spectrum implies, over recent time
    if (sugg.current) {
      const [x, W, H] = fit(sugg.current);
      x.clearRect(0, 0, W, H);
      const n = hist.length;
      for (let i = 0; i < n; i++) { x.fillStyle = colorHex[hist[i].color] || "#1a1f2c"; x.fillRect((i / n) * W, 0, Math.ceil(W / n) + 1, H); }
    }
  }, [telem, hist, barColors, colorHex]);

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
    <div>
      <h2 className={h2}>Live telemetry — what the music says vs what the light does</h2>
      <div className="flex flex-wrap gap-2 mb-3">
        <div className={ro}><span className={roSpan}>BPM</span><b className="text-[15px] tabular-nums">{t && t.bpm > 0 ? t.bpm : "—"}</b></div>
        <div className={ro}><span className={roSpan}>Beat</span><b><i className="inline-block w-3.5 h-3.5 rounded-full transition-transform" style={{ background: beatOn ? "#57d090" : "#2a3142", transform: `scale(${1 + (t?.beat_flash || 0) * 0.6})` }} /></b></div>
        {t?.C != null && <div className={ro}><span className={roSpan}>Threshold C</span><b className="text-[15px] tabular-nums">{t.C}</b></div>}
        {t?.mood != null && <div className={ro}><span className={roSpan}>Mood</span><b className="text-[15px]">{t.mood}</b></div>}
        <div className={ro}><span className={roSpan}>Colour</span><b className="text-[15px]"><i className={dot} style={{ background: colorHex[t?.color || ""] || "#2a3142" }} />{t?.color || "—"}</b></div>
        <div className={ro}><span className={roSpan}>Family</span><b className="text-xs">{t?.family || "—"}</b></div>
        <div className={ro}><span className={roSpan}>Effect</span><b className="text-xs">{t?.mode ? (num2name[t.mode] || "#" + t.mode) : "—"}</b></div>
        <div className={ro}><span className={roSpan}>Dir</span><b className="text-[15px]">{t?.direction === "bwd" ? "◀ back" : "▶ fwd"}</b></div>
      </div>
      <div className={card2 + " mb-4"}>
        <div className={tlabel + " flex items-center justify-between"}>
          <span>Spectrum <span className={note}>(live · whitened, coloured by band)</span></span>
          <span className="flex items-center gap-1.5 text-[11px] text-mute">suggests
            <i className="inline-block w-3 h-3 rounded-full" style={{ background: colorHex[t?.color || ""] || "#2a3142" }} />
            <b className="text-ink">{t?.color || "—"}</b>
          </span>
        </div>
        <canvas ref={spec} className={canvasCls} />
        <div className="text-[10px] text-dim mt-1.5 mb-0.5">suggested colour over recent time →</div>
        <canvas ref={sugg} className="w-full h-4 rounded block bg-panel2" />
      </div>

      {!hasTrack && (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          <div className={card2}>
            <div className={tlabel}>Loudness → Brightness <span className={note}><b className="text-[#7fd0ff]">level(target)</b> · <b className="text-[#5ad28a]">brightness(sent)</b></span></div>
            <canvas ref={lb} className={canvasCls} />
          </div>
          <div className={card2}>
            <div className={tlabel}>Frequency → Colour <span className={note}>(chosen colour over time · line = spectral centroid)</span></div>
            <canvas ref={col} className={canvasCls} />
          </div>
        </div>
      )}
    </div>
  );
}
