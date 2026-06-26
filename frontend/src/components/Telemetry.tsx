import { useEffect, useRef } from "react";
import type { Telemetry as T } from "../api";

export interface HistPoint { level: number; bright: number; color: string; centroid: number }

interface Props {
  telem: T | null;
  hist: HistPoint[];
  colorHex: Record<string, string>;
  barColors: string[];
  num2name: Record<number, string>;
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

export default function Telemetry({ telem, hist, colorHex, barColors, num2name }: Props) {
  const spec = useRef<HTMLCanvasElement>(null);
  const lb = useRef<HTMLCanvasElement>(null);
  const col = useRef<HTMLCanvasElement>(null);

  // spectrum bars come from the backend (precomputed timeline for tracks, live
  // analysis for the mic) — consistent scaling + colours either way
  useEffect(() => {
    if (spec.current && telem?.spectrum) drawBars(spec.current, telem.spectrum, barColors);
  }, [telem, barColors]);

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
  return (
    <div className="telemetry">
      <h2>Live telemetry — what the music says vs what the light does</h2>
      <div className="readouts">
        <div className="ro"><span>BPM</span><b>{t && t.bpm > 0 ? t.bpm : "—"}</b></div>
        <div className="ro"><span>Beat</span><b><i className="beatDot" style={{ background: beatOn ? "#57d090" : "#2a3142", transform: `scale(${1 + (t?.beat_flash || 0) * 0.6})` }} /></b></div>
        {t?.C != null && <div className="ro"><span>Threshold C</span><b>{t.C}</b></div>}
        {t?.mood != null && <div className="ro"><span>Mood</span><b>{t.mood}</b></div>}
        <div className="ro"><span>Colour</span><b><i className="colDot" style={{ background: colorHex[t?.color || ""] || "#2a3142" }} />{t?.color || "—"}</b></div>
        <div className="ro fam"><span>Family</span><b>{t?.family || "—"}</b></div>
        <div className="ro mode"><span>Effect</span><b>{t?.mode ? (num2name[t.mode] || "#" + t.mode) : "—"}</b></div>
        <div className="ro"><span>Dir</span><b>{t?.direction === "bwd" ? "◀ back" : "▶ fwd"}</b></div>
      </div>
      <div className="tgrid">
        <div className="tcard">
          <div className="tlabel">Spectrum <span className="tnote">(bars coloured by frequency→colour band)</span></div>
          <canvas ref={spec} />
        </div>
        <div className="tcard">
          <div className="tlabel">Loudness → Brightness <span className="tnote"><b style={{ color: "#7fd0ff" }}>level(target)</b> · <b style={{ color: "#5ad28a" }}>brightness(sent)</b></span></div>
          <canvas ref={lb} />
        </div>
        <div className="tcard">
          <div className="tlabel">Frequency → Colour <span className="tnote">(chosen colour over time · line = spectral centroid)</span></div>
          <canvas ref={col} />
        </div>
      </div>
    </div>
  );
}
