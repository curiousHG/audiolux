import { useEffect, useRef } from "react";
import type { Plan } from "@/api";
import { fmtTime } from "@/api";

interface Props {
  plan: Plan;
  pos: number;                       // current playback time (s)
  colorHex: Record<string, string>;
  onSeek: (t: number) => void;
}

const GUTTER = 104;                  // left label column
const PADR = 14;
const BR_H = 44;                     // brightness lane
const COL_H = 16;                    // colour lane
const DIR_H = 18;                    // direction-marker lane
const SUB_H = 10;                    // colour sub-lane within a family group
const GROUP_GAP = 8;
const GAP = 8;
const AXIS_H = 18;
const TOP = 6;

// One large graph: y is split into family GROUPS, each group split into colour
// sub-lanes (low→high frequency); x is time. Segments are blocks at (family,
// colour). Direction flips are marked with arrows + faint vertical lines. A
// draggable playhead seeks playback.
export default function TrackTimeline({ plan, pos, colorHex, onSeek }: Props) {
  const cv = useRef<HTMLCanvasElement>(null);
  const dragging = useRef(false);
  const freq = plan.freq_colors?.length ? plan.freq_colors : ["RD", "VT", "BU", "GN", "YE", "WH"];
  const nSub = freq.length;
  const groups = plan.families;

  const colY = TOP + BR_H + GAP;
  const dirY = colY + COL_H + GAP;
  const modesTop = dirY + DIR_H + GAP;
  const groupH = nSub * SUB_H;
  const modesH = groups.length * groupH + Math.max(0, groups.length - 1) * GROUP_GAP;
  const totalH = modesTop + modesH + GAP + AXIS_H;

  // y of a (group index, colour index within freq) sub-lane top
  const subTop = (g: number, ci: number) => modesTop + g * (groupH + GROUP_GAP) + ci * SUB_H;

  useEffect(() => {
    const c = cv.current; if (!c) return;
    const W = (c.width = c.clientWidth);
    const H = (c.height = totalH);
    const x = c.getContext("2d")!;
    const dur = plan.duration || 1;
    const plotW = W - GUTTER - PADR;
    const X = (t: number) => GUTTER + (t / dur) * plotW;

    x.clearRect(0, 0, W, H);
    x.font = "10px system-ui"; x.textBaseline = "middle";
    const lane = (y: number, h: number, c2 = "#0a0c11") => { x.fillStyle = c2; x.fillRect(GUTTER, y, plotW, h); };
    const rlabel = (s: string, y: number, col = "#7b8395") => { x.fillStyle = col; x.textAlign = "right"; x.fillText(s, GUTTER - 8, y); };

    // --- brightness lane ---
    lane(TOP, BR_H); rlabel("Brightness", TOP + BR_H / 2);
    const lv = plan.level, st = plan.sig_t, n = lv.length;
    if (n) {
      x.beginPath(); x.moveTo(GUTTER, TOP + BR_H);
      for (let i = 0; i < n; i++) x.lineTo(X(st[i]), TOP + BR_H - lv[i] * (BR_H - 2));
      x.lineTo(GUTTER + plotW, TOP + BR_H); x.closePath(); x.fillStyle = "#5ad28a22"; x.fill();
      x.beginPath();
      for (let i = 0; i < n; i++) { const px = X(st[i]), py = TOP + BR_H - lv[i] * (BR_H - 2); i ? x.lineTo(px, py) : x.moveTo(px, py); }
      x.strokeStyle = "#5ad28a"; x.lineWidth = 1.4; x.stroke();
    }

    // --- colour lane ---
    rlabel("Colour", colY + COL_H / 2);
    for (let i = 0; i < n; i++) {
      const x0 = X(st[i]), x1 = i + 1 < n ? X(st[i + 1]) : GUTTER + plotW;
      x.fillStyle = colorHex[plan.scolor[i]] || "#333";
      x.fillRect(x0, colY, Math.max(1, x1 - x0) + 0.5, COL_H);
    }

    // --- modes: family groups, each with colour sub-lanes (low→high freq) ---
    groups.forEach((fam, g) => {
      for (let ci = 0; ci < nSub; ci++) {
        const y = subTop(g, ci);
        lane(y, SUB_H - 1, ci % 2 ? "#0b0e14" : "#0a0c11");
        x.fillStyle = colorHex[freq[ci]] || "#444";                 // colour swatch for the lane
        x.fillRect(GUTTER + 1, y + 1, 4, SUB_H - 3);
      }
      // group label centred over its sub-lanes
      rlabel(fam, subTop(g, 0) + groupH / 2, "#c7ccd8");
    });
    for (const s of plan.segments) {
      const g = groups.indexOf(s.family); if (g < 0) continue;
      let ci = freq.indexOf(s.color); if (ci < 0) ci = nSub - 1;
      const y = subTop(g, ci);
      const x0 = X(s.t0), w = Math.max(2, X(s.t1) - x0 - 1);
      x.fillStyle = colorHex[s.color] || "#888";
      x.fillRect(x0, y + 1, w, SUB_H - 2);
      if (s.kind === "strobe") { x.fillStyle = "#0a0c11"; for (let gx = x0 + 2; gx < x0 + w; gx += 4) x.fillRect(gx, y + 1, 1, SUB_H - 2); }
    }

    // --- direction-switch markers ---
    rlabel("Dir", dirY + DIR_H / 2, "#9aa3b5");
    const modesBottom = modesTop + modesH;
    x.textAlign = "center";
    for (const mk of plan.dir_marks || []) {
      const mx = X(mk.t);
      x.strokeStyle = "#ffffff18"; x.lineWidth = 1; x.setLineDash([3, 3]);
      x.beginPath(); x.moveTo(mx, dirY); x.lineTo(mx, modesBottom); x.stroke(); x.setLineDash([]);
      x.fillStyle = mk.fwd ? "#5ad28a" : "#e0a050";
      x.fillText(mk.fwd ? "▶" : "◀", mx, dirY + DIR_H / 2);
    }

    // --- time axis ---
    const ay = modesBottom + GAP + 2;
    x.fillStyle = "#5b6273"; x.textAlign = "center";
    for (let k = 0; k <= 6; k++) { const t = (dur * k) / 6; x.fillText(fmtTime(t), X(t), ay + 7); }

    // --- playhead ---
    const ph = X(Math.max(0, Math.min(pos, dur)));
    x.strokeStyle = "#ffffff"; x.lineWidth = 1.5;
    x.beginPath(); x.moveTo(ph, TOP); x.lineTo(ph, modesBottom); x.stroke();
    x.fillStyle = "#ffffff";
    x.beginPath(); x.moveTo(ph - 4, TOP); x.lineTo(ph + 4, TOP); x.lineTo(ph, TOP + 5); x.closePath(); x.fill();
  }, [plan, pos, colorHex, totalH, groups, freq, nSub, colY, dirY, modesTop, groupH, modesH]);

  function seekAt(clientX: number) {
    const c = cv.current!; const rc = c.getBoundingClientRect();
    const plotW = rc.width - GUTTER - PADR;
    const t = ((clientX - rc.left - GUTTER) / plotW) * plan.duration;
    onSeek(Math.max(0, Math.min(plan.duration, t)));
  }

  return (
    <div className="bg-panel border border-line rounded-xl p-3">
      <div className="text-xs text-[#c7ccd8] font-medium mb-1.5">
        Song timeline <span className="text-[11px] text-dim font-normal">— family groups × colour (low→high freq) over time · ▶◀ = direction switch · drag to seek</span>
      </div>
      <canvas ref={cv} className="w-full block cursor-pointer touch-none" style={{ height: totalH }}
              onPointerDown={(e) => { dragging.current = true; (e.target as HTMLElement).setPointerCapture(e.pointerId); seekAt(e.clientX); }}
              onPointerMove={(e) => { if (dragging.current) seekAt(e.clientX); }}
              onPointerUp={() => { dragging.current = false; }} />
    </div>
  );
}
