import { useEffect, useRef } from "react";
import type { Plan } from "@/api";
import { fmtTime } from "@/api";

interface Props {
  plan: Plan;
  pos: number;                       // current playback time (s)
  colorHex: Record<string, string>;
  onSeek: (t: number) => void;
}

const GUTTER = 92;                   // left label column
const PADR = 12;
const BR_H = 46;                     // brightness lane
const COL_H = 18;                    // colour lane
const ROW_H = 22;                    // mode rows
const GAP = 8;
const AXIS_H = 18;
const TOP = 6;

// Track timeline: full-song precomputed signals + the mode plan as a piano-roll
// (rows = families, colour = light colour, x = time), with a draggable playhead.
export default function TrackTimeline({ plan, pos, colorHex, onSeek }: Props) {
  const cv = useRef<HTMLCanvasElement>(null);
  const dragging = useRef(false);
  const rows = plan.families.length;
  const modesTop = TOP + BR_H + GAP + COL_H + GAP;
  const totalH = modesTop + rows * ROW_H + GAP + AXIS_H;

  useEffect(() => {
    const c = cv.current; if (!c) return;
    const W = (c.width = c.clientWidth);
    const H = (c.height = totalH);
    const x = c.getContext("2d")!;
    const dur = plan.duration || 1;
    const plotW = W - GUTTER - PADR;
    const X = (t: number) => GUTTER + (t / dur) * plotW;

    x.clearRect(0, 0, W, H);
    x.font = "10px system-ui";
    x.textBaseline = "middle";

    const lane = (y: number, h: number) => { x.fillStyle = "#0a0c11"; x.fillRect(GUTTER, y, plotW, h); };
    const rlabel = (s: string, y: number) => { x.fillStyle = "#7b8395"; x.textAlign = "right"; x.fillText(s, GUTTER - 8, y); };

    // --- brightness lane (area) ---
    lane(TOP, BR_H);
    rlabel("Brightness", TOP + BR_H / 2);
    const lv = plan.level, st = plan.sig_t, n = lv.length;
    if (n) {
      x.beginPath(); x.moveTo(GUTTER, TOP + BR_H);
      for (let i = 0; i < n; i++) x.lineTo(X(st[i]), TOP + BR_H - lv[i] * (BR_H - 2));
      x.lineTo(GUTTER + plotW, TOP + BR_H); x.closePath();
      x.fillStyle = "#5ad28a22"; x.fill();
      x.beginPath();
      for (let i = 0; i < n; i++) { const px = X(st[i]), py = TOP + BR_H - lv[i] * (BR_H - 2); i ? x.lineTo(px, py) : x.moveTo(px, py); }
      x.strokeStyle = "#5ad28a"; x.lineWidth = 1.4; x.stroke();
    }

    // --- colour lane ---
    const colY = TOP + BR_H + GAP;
    rlabel("Colour", colY + COL_H / 2);
    for (let i = 0; i < n; i++) {
      const x0 = X(st[i]), x1 = i + 1 < n ? X(st[i + 1]) : GUTTER + plotW;
      x.fillStyle = colorHex[plan.scolor[i]] || "#333";
      x.fillRect(x0, colY, Math.max(1, x1 - x0) + 0.5, COL_H);
    }

    // --- mode rows (piano-roll) ---
    plan.families.forEach((fam, r) => {
      const y = modesTop + r * ROW_H;
      lane(y + 2, ROW_H - 4);
      rlabel(fam, y + ROW_H / 2);
    });
    for (const s of plan.segments) {
      const r = plan.families.indexOf(s.family); if (r < 0) continue;
      const y = modesTop + r * ROW_H + 3;
      const x0 = X(s.t0), x1 = X(s.t1), w = Math.max(2, x1 - x0 - 1);
      x.fillStyle = colorHex[s.color] || "#888";
      x.fillRect(x0, y, w, ROW_H - 6);
      if (s.kind === "strobe") {                 // strobe = striped to read as flashing
        x.fillStyle = "#0a0c11";
        for (let gx = x0 + 2; gx < x0 + w; gx += 4) x.fillRect(gx, y, 1.5, ROW_H - 6);
      }
    }

    // --- time axis ---
    const ay = modesTop + rows * ROW_H + GAP + 2;
    x.fillStyle = "#5b6273"; x.textAlign = "center";
    for (let k = 0; k <= 4; k++) {
      const t = (dur * k) / 4;
      x.fillText(fmtTime(t), X(t), ay + 7);
    }

    // --- playhead ---
    const ph = X(Math.max(0, Math.min(pos, dur)));
    x.strokeStyle = "#ffffff"; x.lineWidth = 1.5;
    x.beginPath(); x.moveTo(ph, TOP); x.lineTo(ph, modesTop + rows * ROW_H); x.stroke();
    x.fillStyle = "#ffffff";
    x.beginPath(); x.moveTo(ph - 4, TOP); x.lineTo(ph + 4, TOP); x.lineTo(ph, TOP + 5); x.closePath(); x.fill();
  }, [plan, pos, colorHex, totalH, rows]);

  function seekAt(clientX: number) {
    const c = cv.current!; const rc = c.getBoundingClientRect();
    const plotW = rc.width - GUTTER - PADR;
    const t = ((clientX - rc.left - GUTTER) / plotW) * plan.duration;
    onSeek(Math.max(0, Math.min(plan.duration, t)));
  }

  return (
    <div className="bg-panel border border-line rounded-xl p-3">
      <div className="text-xs text-[#c7ccd8] font-medium mb-1.5">
        Song timeline <span className="text-[11px] text-dim font-normal">— drag the playhead to seek; the lights jump with it</span>
      </div>
      <canvas ref={cv} className="w-full block cursor-pointer touch-none" style={{ height: totalH }}
              onPointerDown={(e) => { dragging.current = true; (e.target as HTMLElement).setPointerCapture(e.pointerId); seekAt(e.clientX); }}
              onPointerMove={(e) => { if (dragging.current) seekAt(e.clientX); }}
              onPointerUp={() => { dragging.current = false; }} />
    </div>
  );
}
