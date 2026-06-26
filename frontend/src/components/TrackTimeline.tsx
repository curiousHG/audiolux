import { useRef } from "react";
import { scaleLinear } from "@visx/scale";
import { AxisBottom } from "@visx/axis";
import { ParentSize } from "@visx/responsive";
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
const BR_H = 40, COL_H = 14, DIR_H = 16, SUB_H = 9, GROUP_GAP = 7, GAP = 7, AXIS_H = 22;
const OV_H = 46, OV_STRIP = 12;

export default function TrackTimeline(props: Props) {
  return (
    <div className="bg-panel border border-line rounded-xl p-3">
      <div className="text-xs text-[#c7ccd8] font-medium mb-2">
        Song timeline <span className="text-[11px] text-dim font-normal">— 30 s window, centred playhead · family × colour (low→high freq) · ▶◀ direction · drag to seek</span>
      </div>
      <ParentSize>{({ width }) => (width > 0 ? <Chart {...props} width={width} /> : null)}</ParentSize>
    </div>
  );
}

function Chart({ plan, pos, colorHex, onSeek, width }: Props & { width: number }) {
  const freq = plan.freq_colors?.length ? plan.freq_colors : ["RD", "VT", "BU", "GN", "YE", "WH"];
  const nSub = freq.length;
  const groups = plan.families;
  const dur = plan.duration || 1;
  const W = width;

  const colY = TOP + BR_H + GAP;
  const dirY = colY + COL_H + GAP;
  const modesTop = dirY + DIR_H + GAP;
  const groupH = nSub * SUB_H;
  const modesH = groups.length * groupH + Math.max(0, groups.length - 1) * GROUP_GAP;
  const modesBottom = modesTop + modesH;
  const mainH = modesBottom + GAP + AXIS_H;
  const subTop = (g: number, ci: number) => modesTop + g * (groupH + GROUP_GAP) + ci * SUB_H;

  // 30 s window centred on the playhead (clamped to the song ends)
  const winStart = Math.max(0, Math.min(pos - WIN / 2, Math.max(0, dur - WIN)));
  const winEnd = winStart + WIN;
  const x = scaleLinear({ domain: [winStart, winEnd], range: [GUTTER, W - PADR] });
  const xAll = scaleLinear({ domain: [0, dur], range: [6, W - 6] });

  const mainRef = useRef<SVGSVGElement>(null);
  const ovRef = useRef<SVGSVGElement>(null);
  const drag = useRef<null | "main" | "ov">(null);
  const seekFrom = (svg: SVGSVGElement | null, scale: any, clientX: number) => {
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    const t = scale.invert(clientX - r.left);
    onSeek(Math.max(0, Math.min(dur, t)));
  };

  const st = plan.sig_t, lv = plan.level;
  const rlabel = (s: string, y: number, col = "#7b8395") =>
    <text x={GUTTER - 8} y={y} fill={col} fontSize={10} textAnchor="end" dominantBaseline="middle">{s}</text>;

  // brightness path within the window
  let bpath = "";
  for (let i = 0; i < st.length; i++) {
    if (st[i] < winStart - 1 || st[i] > winEnd + 1) continue;
    bpath += `${bpath ? "L" : "M"}${x(st[i]).toFixed(1)} ${(TOP + BR_H - lv[i] * (BR_H - 2)).toFixed(1)} `;
  }
  // overview brightness sparkline
  let ovpath = "";
  for (let i = 0; i < st.length; i++) {
    ovpath += `${ovpath ? "L" : "M"}${xAll(st[i]).toFixed(1)} ${(OV_H - lv[i] * (OV_H - OV_STRIP - 2)).toFixed(1)} `;
  }

  return (
    <>
      <svg ref={mainRef} width={W} height={mainH} className="block touch-none cursor-pointer select-none"
           onPointerDown={(e) => { drag.current = "main"; (e.target as Element).setPointerCapture?.(e.pointerId); seekFrom(mainRef.current, x, e.clientX); }}
           onPointerMove={(e) => { if (drag.current === "main") seekFrom(mainRef.current, x, e.clientX); }}
           onPointerUp={() => { drag.current = null; }}>
        {/* brightness lane */}
        <rect x={GUTTER} y={TOP} width={W - PADR - GUTTER} height={BR_H} fill="#0a0c11" />
        {rlabel("Brightness", TOP + BR_H / 2)}
        <path d={`${bpath}L${(W - PADR)} ${TOP + BR_H} L${GUTTER} ${TOP + BR_H} Z`} fill="#5ad28a22" />
        <path d={bpath} fill="none" stroke="#5ad28a" strokeWidth={1.4} />

        {/* colour lane */}
        {rlabel("Colour", colY + COL_H / 2)}
        {st.map((t, i) => (t >= winStart - 1 && t <= winEnd) ? (
          <rect key={i} x={x(t)} y={colY} width={Math.max(1, (i + 1 < st.length ? x(st[i + 1]) : x(winEnd)) - x(t)) + 0.5}
                height={COL_H} fill={colorHex[plan.scolor[i]] || "#333"} />
        ) : null)}

        {/* direction markers */}
        {rlabel("Dir", dirY + DIR_H / 2, "#9aa3b5")}
        {(plan.dir_marks || []).filter((m) => m.t >= winStart && m.t <= winEnd).map((m, k) => (
          <g key={k}>
            <line x1={x(m.t)} y1={dirY} x2={x(m.t)} y2={modesBottom} stroke="#ffffff18" strokeDasharray="3 3" />
            <text x={x(m.t)} y={dirY + DIR_H / 2} fill={m.fwd ? "#5ad28a" : "#e0a050"} fontSize={11} textAnchor="middle" dominantBaseline="middle">{m.fwd ? "▶" : "◀"}</text>
          </g>
        ))}

        {/* mode rows: family groups × colour sub-lanes */}
        {groups.map((fam, g) => (
          <g key={fam}>
            {freq.map((c, ci) => (
              <g key={ci}>
                <rect x={GUTTER} y={subTop(g, ci)} width={W - PADR - GUTTER} height={SUB_H - 1} fill={ci % 2 ? "#0b0e14" : "#0a0c11"} />
                <rect x={GUTTER + 1} y={subTop(g, ci) + 1} width={4} height={SUB_H - 3} fill={colorHex[c] || "#444"} />
              </g>
            ))}
            {rlabel(fam, subTop(g, 0) + groupH / 2, "#c7ccd8")}
          </g>
        ))}
        {plan.segments.filter((s) => s.t1 > winStart && s.t0 < winEnd && groups.includes(s.family)).map((s, k) => {
          const g = groups.indexOf(s.family);
          let ci = freq.indexOf(s.color); if (ci < 0) ci = nSub - 1;
          const x0 = x(Math.max(s.t0, winStart)), x1 = x(Math.min(s.t1, winEnd));
          return <rect key={k} x={x0} y={subTop(g, ci) + 1} width={Math.max(2, x1 - x0)} height={SUB_H - 2}
                       fill={colorHex[s.color] || "#888"} opacity={s.kind === "strobe" ? 0.7 : 1} />;
        })}

        <AxisBottom top={modesBottom + 2} scale={x} numTicks={6} stroke="#2a3142" tickStroke="#2a3142"
                    tickFormat={(v) => fmtTime(v as number)}
                    tickLabelProps={() => ({ fill: "#5b6273", fontSize: 9, textAnchor: "middle" })} />

        {/* playhead (centred) */}
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
                height={OV_STRIP} fill={colorHex[plan.scolor[i]] || "#333"} />
        ))}
        <path d={ovpath} fill="none" stroke="#5ad28a" strokeWidth={1} opacity={0.8} />
        {/* current window */}
        <rect x={xAll(winStart)} y={0} width={Math.max(2, xAll(winEnd) - xAll(winStart))} height={OV_H}
              fill="#5b8cff22" stroke="#5b8cff" strokeWidth={1} />
        <line x1={xAll(pos)} y1={0} x2={xAll(pos)} y2={OV_H} stroke="#fff" strokeWidth={1} />
      </svg>
    </>
  );
}
