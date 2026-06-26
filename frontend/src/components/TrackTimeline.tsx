import { useEffect, useRef, useState } from "react";
import { scaleLinear } from "@visx/scale";
import { AxisBottom } from "@visx/axis";
import type { Plan } from "@/api";
import { fmtTime } from "@/api";

interface Props {
  plan: Plan;
  pos: number;
  colorHex: Record<string, string>;
  onSeek: (t: number) => void;
}

const WIN = 30;                      // seconds visible at once
const GUTTER = 96, PADR = 12, TOP = 4;
const BPM_H = 28, BR_H = 36, COL_H = 12, DIR_H = 14, MODE_H = 44, SUB_H = 9;
const GAP = 8, GROUP_GAP = 8, AXIS_H = 20, OV_H = 44, OV_STRIP = 12;

function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const update = () => setW(el.clientWidth);
    update();
    const ro = new ResizeObserver(update); ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

export default function TrackTimeline(props: Props) {
  const [ref, w] = useWidth();
  return (
    <div className="bg-panel border border-line rounded-xl p-3">
      <div className="text-xs text-[#c7ccd8] font-medium mb-2">
        Song timeline <span className="text-[11px] text-dim font-normal">— 30 s window, centred playhead · drag to seek · overview below to jump</span>
      </div>
      <div ref={ref}>{w > 0 && <Chart {...props} width={w} />}</div>
    </div>
  );
}

function Chart({ plan, pos, colorHex, onSeek, width }: Props & { width: number }) {
  const freq = plan.freq_colors?.length ? plan.freq_colors : ["RD", "VT", "BU", "GN", "YE", "WH"];
  const nSub = freq.length;
  const groups = plan.families;
  const dur = plan.duration || 1;
  const W = width;
  const plotW = W - PADR - GUTTER;

  const bpmY = TOP;
  const brY = bpmY + BPM_H + GAP;
  const colY = brY + BR_H + GAP;
  const dirY = colY + COL_H + GAP;
  const modeLineY = dirY + DIR_H + GAP;
  const modesTop = modeLineY + MODE_H + GAP;
  const groupH = nSub * SUB_H;
  const modesH = groups.length * groupH + Math.max(0, groups.length - 1) * GROUP_GAP;
  const modesBottom = modesTop + modesH;
  const mainH = modesBottom + GAP + AXIS_H;
  const subTop = (g: number, ci: number) => modesTop + g * (groupH + GROUP_GAP) + ci * SUB_H;

  const winStart = Math.max(0, Math.min(pos - WIN / 2, Math.max(0, dur - WIN)));
  const winEnd = winStart + WIN;
  const x = scaleLinear({ domain: [winStart, winEnd], range: [GUTTER, W - PADR] });
  const xAll = scaleLinear({ domain: [0, dur], range: [6, W - 6] });

  const mainRef = useRef<SVGSVGElement>(null);
  const ovRef = useRef<SVGSVGElement>(null);
  const drag = useRef<null | "main" | "ov">(null);
  const seekFrom = (svg: SVGSVGElement | null, scale: any, clientX: number) => {
    if (!svg) return;
    const t = scale.invert(clientX - svg.getBoundingClientRect().left);
    onSeek(Math.max(0, Math.min(dur, t)));
  };

  const st = plan.sig_t, lv = plan.level, bp = plan.bpm_curve || [];
  const inWin = (i: number) => st[i] >= winStart - 1 && st[i] <= winEnd + 1;

  const bpmVals = bp.filter((v) => v > 0);
  const bMin = bpmVals.length ? Math.min(...bpmVals) - 4 : 60;
  const bMax = bpmVals.length ? Math.max(...bpmVals) + 4 : 180;
  const yBpm = (v: number) => bpmY + BPM_H - 2 - ((v - bMin) / Math.max(1, bMax - bMin)) * (BPM_H - 4);

  let bpath = "", bpmPath = "";
  for (let i = 0; i < st.length; i++) {
    if (!inWin(i)) continue;
    bpath += `${bpath ? "L" : "M"}${x(st[i]).toFixed(1)} ${(brY + BR_H - lv[i] * (BR_H - 2)).toFixed(1)} `;
    if (bp[i] > 0) bpmPath += `${bpmPath ? "L" : "M"}${x(st[i]).toFixed(1)} ${yBpm(bp[i]).toFixed(1)} `;
  }
  let ovpath = "";
  for (let i = 0; i < st.length; i++)
    ovpath += `${ovpath ? "L" : "M"}${xAll(st[i]).toFixed(1)} ${(OV_H - lv[i] * (OV_H - OV_STRIP - 2)).toFixed(1)} `;

  const modeSegs = plan.segments.filter((s) => s.kind === "mode" && s.mode != null);
  const mm = modeSegs.map((s) => s.mode as number);
  const mMin = mm.length ? Math.min(...mm) : 1, mMax = mm.length ? Math.max(...mm) : 200;
  const yMode = (m: number) => modeLineY + MODE_H - 3 - ((m - mMin) / Math.max(1, mMax - mMin)) * (MODE_H - 9);

  const winSegs = plan.segments.filter((s) => s.t1 > winStart && s.t0 < winEnd);

  // actual strip colour over time: mode segments hold their colour; STROBE segments
  // flash the live per-frame colour, so use scolor[i] inside them.
  const segT0 = plan.segments.map((s) => s.t0);
  const segAt = (t: number) => {
    let lo = 0, hi = segT0.length - 1, idx = 0;
    while (lo <= hi) { const mid = (lo + hi) >> 1; if (segT0[mid] <= t) { idx = mid; lo = mid + 1; } else hi = mid - 1; }
    return plan.segments[idx];
  };
  const colourAt = (i: number) => {
    const s = segAt(st[i]);
    return s && s.kind === "mode" ? s.color : plan.scolor[i];
  };
  const labels: Array<[string, number, string]> = [
    ["BPM", bpmY + BPM_H / 2, "#7b8395"],
    ["Brightness", brY + BR_H / 2, "#7b8395"],
    ["Colour", colY + COL_H / 2, "#7b8395"],
    ["Dir", dirY + DIR_H / 2, "#9aa3b5"],
    ["Mode", modeLineY + MODE_H / 2, "#7b8395"],
  ];

  return (
    <>
      <svg ref={mainRef} width={W} height={mainH} className="block touch-none cursor-pointer select-none"
           onPointerDown={(e) => { drag.current = "main"; (e.target as Element).setPointerCapture?.(e.pointerId); seekFrom(mainRef.current, x, e.clientX); }}
           onPointerMove={(e) => { if (drag.current === "main") seekFrom(mainRef.current, x, e.clientX); }}
           onPointerUp={() => { drag.current = null; }}>
        <defs><clipPath id="tlplot"><rect x={GUTTER} y={0} width={plotW} height={mainH} /></clipPath></defs>

        {/* lane backgrounds (with gaps between = clean dividers) */}
        <rect x={GUTTER} y={bpmY} width={plotW} height={BPM_H} fill="#0a0c11" />
        <rect x={GUTTER} y={brY} width={plotW} height={BR_H} fill="#0a0c11" />
        <rect x={GUTTER} y={colY} width={plotW} height={COL_H} fill="#0a0c11" />
        <rect x={GUTTER} y={dirY} width={plotW} height={DIR_H} fill="#0c0f16" />
        <rect x={GUTTER} y={modeLineY} width={plotW} height={MODE_H} fill="#0a0c11" />
        {groups.map((fam, g) => freq.map((_, ci) => (
          <rect key={`${fam}-${ci}`} x={GUTTER} y={subTop(g, ci)} width={plotW} height={SUB_H - 1} fill={ci % 2 ? "#0b0e14" : "#0a0c11"} />
        )))}

        {/* all data clipped to the plot area (never enters the gutter) */}
        <g clipPath="url(#tlplot)">
          <path d={bpmPath} fill="none" stroke="#00d8e6" strokeWidth={1.4} />
          <path d={`${bpath}L${W - PADR} ${brY + BR_H} L${GUTTER} ${brY + BR_H} Z`} fill="#5ad28a22" />
          <path d={bpath} fill="none" stroke="#5ad28a" strokeWidth={1.4} />

          {/* colour lane — the strip's ACTUAL colour over time (held for modes,
              per-frame for strobe) so it matches what you see on the strip */}
          {st.map((t, i) => (t >= winStart - 1 && t <= winEnd) ? (
            <rect key={i} x={x(t)} y={colY} width={Math.max(1, (i + 1 < st.length ? x(st[i + 1]) : x(winEnd)) - x(t)) + 0.5}
                  height={COL_H} fill={colorHex[colourAt(i)] || "#333"} />
          ) : null)}

          {/* direction markers */}
          {(plan.dir_marks || []).filter((m) => m.t >= winStart && m.t <= winEnd).map((m, k) => (
            <g key={k}>
              <line x1={x(m.t)} y1={dirY} x2={x(m.t)} y2={modesBottom} stroke="#ffffff14" strokeDasharray="3 3" />
              <text x={x(m.t)} y={dirY + DIR_H / 2} fill={m.fwd ? "#5ad28a" : "#e0a050"} fontSize={11} textAnchor="middle" dominantBaseline="middle">{m.fwd ? "▶" : "◀"}</text>
            </g>
          ))}

          {/* mode line + dots */}
          {modeSegs.map((s, k) => {
            const next = modeSegs[k + 1];
            // only connect temporally-adjacent modes (no line across a strobe gap)
            return next && next.t0 - s.t1 < 0.4 && next.t0 < winEnd && s.t1 > winStart ? (
              <line key={"c" + k} x1={x(Math.min(s.t1, winEnd))} y1={yMode(s.mode!)} x2={x(Math.max(next.t0, winStart))} y2={yMode(next.mode!)} stroke="#ffffff22" strokeWidth={1} />
            ) : null;
          })}
          {modeSegs.filter((s) => s.t1 > winStart && s.t0 < winEnd).map((s, k) => (
            <g key={k}>
              <line x1={x(Math.max(s.t0, winStart))} y1={yMode(s.mode!)} x2={x(Math.min(s.t1, winEnd))} y2={yMode(s.mode!)} stroke={colorHex[s.color] || "#888"} strokeWidth={2} />
              {s.t0 >= winStart - 0.2 && <circle cx={x(s.t0)} cy={yMode(s.mode!)} r={3} fill={colorHex[s.color] || "#888"} stroke="#0a0c11" />}
            </g>
          ))}

          {/* piano-roll: family groups × colour sub-lanes */}
          {groups.map((fam, g) => freq.map((c, ci) => (
            <rect key={`sw-${fam}-${ci}`} x={GUTTER + 1} y={subTop(g, ci) + 1} width={4} height={SUB_H - 3} fill={colorHex[c] || "#444"} />
          )))}
          {/* mode segments: one block in their colour sub-lane */}
          {winSegs.filter((s) => s.kind === "mode" && groups.includes(s.family)).map((s, k) => {
            const g = groups.indexOf(s.family);
            let ci = freq.indexOf(s.color); if (ci < 0) ci = nSub - 1;
            const x0 = x(Math.max(s.t0, winStart)), x1 = x(Math.min(s.t1, winEnd));
            return <rect key={k} x={x0} y={subTop(g, ci) + 1} width={Math.max(2, x1 - x0)} height={SUB_H - 2} fill={colorHex[s.color] || "#888"} />;
          })}
          {/* strobe segments: per-frame colour scattered across the Colour-Strobe sub-lanes */}
          {groups.includes("Colour Strobe") && st.map((t, i) => {
            if (t < winStart - 1 || t > winEnd) return null;
            const s = segAt(t); if (!s || s.kind !== "strobe") return null;
            const g = groups.indexOf("Colour Strobe");
            let ci = freq.indexOf(plan.scolor[i]); if (ci < 0) ci = nSub - 1;
            const w = Math.max(1.5, (i + 1 < st.length ? x(st[i + 1]) : x(winEnd)) - x(t));
            return <rect key={"sb" + i} x={x(t)} y={subTop(g, ci) + 1} width={w} height={SUB_H - 2} fill={colorHex[plan.scolor[i]] || "#888"} />;
          })}
        </g>

        <AxisBottom top={modesBottom + 2} scale={x} numTicks={6} stroke="#2a3142" tickStroke="#2a3142"
                    tickFormat={(v) => fmtTime(v as number)}
                    tickLabelProps={() => ({ fill: "#5b6273", fontSize: 9, textAnchor: "middle" })} />

        {/* y-axis labels LAST (on top, in the gutter — clip keeps data out of here) */}
        {labels.map(([s, y, col], i) => (
          <text key={i} x={GUTTER - 8} y={y} fill={col} fontSize={10} textAnchor="end" dominantBaseline="middle">{s}</text>
        ))}
        {groups.map((fam, g) => (
          <text key={fam} x={GUTTER - 8} y={subTop(g, 0) + groupH / 2} fill="#c7ccd8" fontSize={10} textAnchor="end" dominantBaseline="middle">{fam}</text>
        ))}

        {/* playhead */}
        <line x1={x(pos)} y1={TOP} x2={x(pos)} y2={modesBottom} stroke="#fff" strokeWidth={1.5} />
        <polygon points={`${x(pos) - 4},${TOP} ${x(pos) + 4},${TOP} ${x(pos)},${TOP + 5}`} fill="#fff" />
      </svg>

      {/* overview / window selector */}
      <div className="text-[10px] text-dim mt-2 mb-1">overview — click or drag to jump anywhere</div>
      <svg ref={ovRef} width={W} height={OV_H} className="block touch-none cursor-pointer select-none rounded bg-panel2"
           onPointerDown={(e) => { drag.current = "ov"; (e.target as Element).setPointerCapture?.(e.pointerId); seekFrom(ovRef.current, xAll, e.clientX); }}
           onPointerMove={(e) => { if (drag.current === "ov") seekFrom(ovRef.current, xAll, e.clientX); }}
           onPointerUp={() => { drag.current = null; }}>
        {st.map((t, i) => (
          <rect key={i} x={xAll(t)} y={0} width={Math.max(1, (i + 1 < st.length ? xAll(st[i + 1]) : W - 6) - xAll(t)) + 0.5}
                height={OV_STRIP} fill={colorHex[colourAt(i)] || "#333"} />
        ))}
        <path d={ovpath} fill="none" stroke="#5ad28a" strokeWidth={1} opacity={0.8} />
        <rect x={xAll(winStart)} y={0} width={Math.max(2, xAll(winEnd) - xAll(winStart))} height={OV_H}
              fill="#5b8cff22" stroke="#5b8cff" strokeWidth={1} />
        <line x1={xAll(pos)} y1={0} x2={xAll(pos)} y2={OV_H} stroke="#fff" strokeWidth={1} />
      </svg>
    </>
  );
}
