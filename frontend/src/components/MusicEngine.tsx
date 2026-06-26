import { useState } from "react";
import type { FamilyInfo } from "../api";
import { h2, row, btn, btnSmall, label, val, cx } from "../ui";

const famBtn = "shrink-0 px-[11px] py-[7px] text-xs rounded-[9px] bg-btn2 text-ink cursor-pointer transition-colors hover:bg-btn";

interface Props {
  act: (u: string) => void;
  families: FamilyInfo[];
  micOn: boolean;
  onMicChange: (on: boolean) => void;
}

const REACTIONS = [
  ["react_bright", "Brightness"],
  ["react_speed", "Speed"],
  ["switch_modes", "Switch modes"],
  ["use_direction", "Direction"],
] as const;

export default function MusicEngine({ act, families, micOn, onMicChange }: Props) {
  const [fams, setFams] = useState<Set<string>>(new Set(["Run", "Trailing"]));
  const [react, setReact] = useState<Record<string, boolean>>({
    react_bright: true, react_speed: true, switch_modes: true, use_direction: true,
  });
  const [sens, setSens] = useState(1.5);
  const [bps, setBps] = useState(4);
  const [floor, setFloor] = useState(12);

  function toggleFam(f: string) {
    const next = new Set(fams);
    next.has(f) ? next.delete(f) : next.add(f);
    setFams(next);
    act("/api/music/config?families=" + encodeURIComponent([...next].join(",")));
  }
  function toggleReact(key: string) {
    const v = !react[key];
    setReact({ ...react, [key]: v });
    act(`/api/music/config?${key}=${v}`);
  }

  return (
    <section className="min-w-0">
      <h2 className={h2}>Music Engine (mic)</h2>
      <div className={cx(row, "mt-0")}>
        <button className={cx(btn, micOn && "!bg-on")} onClick={() => onMicChange(!micOn)}>
          🎵 Music Engine (mic): {micOn ? "ON" : "OFF"}
        </button>
      </div>
      {micOn && (
        <>
          <label className={label}>Families to cycle (colour by frequency)</label>
          <div className="flex flex-wrap gap-1.5">
            {families.map((f) => (
              <button key={f.family} className={cx(famBtn, fams.has(f.family) && "!bg-on")}
                      style={{ opacity: f.color_react ? 1 : 0.72 }}
                      title={f.color_react ? "frequency picks colour: " + f.colors.join(" ") : "no single colours — uses 7-colour/combo"}
                      onClick={() => toggleFam(f.family)}>
                {f.family}
              </button>
            ))}
          </div>
          <label className={label}>Reactions</label>
          <div className="flex flex-wrap gap-2 mt-1">
            {REACTIONS.map(([key, lbl]) => (
              <button key={key} className={cx(btnSmall, react[key] && "!bg-on")} onClick={() => toggleReact(key)}>
                {lbl}
              </button>
            ))}
          </div>
          <label className={label}>Beat sensitivity (base C) <span className={val}>{sens.toFixed(2)}</span></label>
          <input type="range" min={110} max={240} value={sens * 100}
                 onChange={(e) => setSens(+e.target.value / 100)}
                 onMouseUp={() => act("/api/music/config?sensitivity=" + sens)} />
          <label className={label}>Mode change every <span className={val}>{bps}</span> beats</label>
          <input type="range" min={1} max={16} value={bps}
                 onChange={(e) => setBps(+e.target.value)}
                 onMouseUp={() => act("/api/music/config?beats_per_switch=" + bps)} />
          <label className={label}>Brightness floor <span className={val}>{floor}</span>%</label>
          <input type="range" min={0} max={80} value={floor}
                 onChange={(e) => setFloor(+e.target.value)}
                 onMouseUp={() => act("/api/music/config?bright_floor=" + floor)} />
        </>
      )}
    </section>
  );
}
