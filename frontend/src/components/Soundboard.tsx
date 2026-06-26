import { useEffect, useRef } from "react";
import { h2 } from "../ui";

const padCls = "h-[62px] rounded-xl border border-black/30 cursor-pointer flex flex-col items-center justify-center text-xs font-semibold text-white select-none transition-[transform,filter] active:scale-[.93] active:brightness-150 [text-shadow:0_1px_3px_#0008]";

interface Pad { label: string; key: string; hex: string; note?: number; fx?: "kick" | "snare" | "hat"; mode?: number }

const PADS: Pad[] = [
  { label: "Red", key: "a", hex: "ff2030", note: 262 }, { label: "Orange", key: "s", hex: "ff7a00", note: 294 },
  { label: "Yellow", key: "d", hex: "ffd400", note: 330 }, { label: "Green", key: "f", hex: "33dd44", note: 392 },
  { label: "Cyan", key: "g", hex: "00d8e6", note: 440 }, { label: "Blue", key: "h", hex: "3060ff", note: 523 },
  { label: "Violet", key: "j", hex: "a000ff", note: 587 }, { label: "White", key: "k", hex: "ffffff", note: 659 },
  { label: "Kick", key: "z", hex: "ff0000", fx: "kick" }, { label: "Snare", key: "x", hex: "ffffff", fx: "snare" },
  { label: "Hat", key: "c", hex: "00ffd0", fx: "hat" }, { label: "Strobe", key: "v", hex: "ffffff", mode: 80 },
];

function darken(hex: string, f: number) {
  const n = parseInt(hex, 16);
  return `rgb(${(((n >> 16) & 255) * f) | 0},${(((n >> 8) & 255) * f) | 0},${((n & 255) * f) | 0})`;
}

export default function Soundboard({ act }: { act: (u: string) => void }) {
  const ac = useRef<AudioContext | null>(null);
  const els = useRef<Record<string, HTMLDivElement | null>>({});

  function ctx() {
    if (!ac.current) ac.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    if (ac.current.state === "suspended") ac.current.resume();
    return ac.current;
  }
  function tone(f: number, dur = 0.28) {
    const a = ctx(), o = a.createOscillator(), g = a.createGain();
    o.type = "triangle"; o.frequency.value = f;
    g.gain.setValueAtTime(1e-4, a.currentTime);
    g.gain.exponentialRampToValueAtTime(0.4, a.currentTime + 0.01);
    g.gain.exponentialRampToValueAtTime(1e-4, a.currentTime + dur);
    o.connect(g).connect(a.destination); o.start(); o.stop(a.currentTime + dur);
  }
  function kick() {
    const a = ctx(), o = a.createOscillator(), g = a.createGain();
    o.frequency.setValueAtTime(150, a.currentTime);
    o.frequency.exponentialRampToValueAtTime(50, a.currentTime + 0.12);
    g.gain.setValueAtTime(0.85, a.currentTime);
    g.gain.exponentialRampToValueAtTime(1e-3, a.currentTime + 0.22);
    o.connect(g).connect(a.destination); o.start(); o.stop(a.currentTime + 0.22);
  }
  function noise(dur = 0.16, hp = false) {
    const a = ctx(), n = a.createBufferSource();
    const buf = a.createBuffer(1, a.sampleRate * dur, a.sampleRate), d = buf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    n.buffer = buf;
    const g = a.createGain();
    g.gain.setValueAtTime(0.5, a.currentTime);
    g.gain.exponentialRampToValueAtTime(1e-3, a.currentTime + dur);
    let node: AudioNode = n;
    if (hp) { const fl = a.createBiquadFilter(); fl.type = "highpass"; fl.frequency.value = 7000; node.connect(fl); node = fl; }
    node.connect(g).connect(a.destination); n.start(); n.stop(a.currentTime + dur);
  }
  function fire(p: Pad) {
    const el = els.current[p.key];
    if (el) { el.classList.add("pad-hit"); setTimeout(() => el.classList.remove("pad-hit"), 110); }
    if (p.fx === "kick") kick(); else if (p.fx === "snare") noise(0.18); else if (p.fx === "hat") noise(0.05, true); else if (p.note) tone(p.note);
    if (p.mode) act("/api/mode?m=" + p.mode); else act("/api/color?hex=" + p.hex);
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.repeat || ["INPUT", "SELECT"].includes((e.target as HTMLElement).tagName)) return;
      const p = PADS.find((x) => x.key === e.key.toLowerCase());
      if (p) { e.preventDefault(); fire(p); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  return (
    <div>
      <h2 className={h2}>Soundboard <span className="normal-case tracking-normal text-dim font-normal">— click or use your keyboard</span></h2>
      <div className="grid grid-cols-4 gap-2">
        {PADS.map((p) => (
          <div key={p.key} ref={(e) => { els.current[p.key] = e; }} className={padCls}
               style={{ background: darken(p.hex, 0.62) }} onClick={() => fire(p)}>
            {p.label}<span className="text-[10px] font-normal opacity-80 mt-[3px]">{p.key.toUpperCase()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
