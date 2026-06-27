import { useEffect, useRef, useState } from "react";

// The behind-the-scenes pipeline, audio -> strip. Single-line plain labels so every
// node measures reliably and lays out (no HTML labels / multi-line measurement).
const DEF = `flowchart TB
  classDef src fill:#1a2233,stroke:#5b8cff,color:#e7e9ee;
  classDef feat fill:#141823,stroke:#2a3142,color:#cdd2dc;
  classDef dec fill:#15212e,stroke:#2f6f8f,color:#dfe6ee;
  classDef out fill:#1c1633,stroke:#a05cff,color:#efe7ff;
  classDef strip fill:#10261a,stroke:#3ad07f,color:#dff7e8;

  A["🎵 YouTube audio"]:::src --> FFT["resample · STFT"]:::feat
  FFT --> RMS["loudness"]:::feat
  FFT --> BANDS["whitened bands"]:::feat
  FFT --> ONSET["onset envelope"]:::feat

  RMS --> BRIGHT["brightness"]:::dec
  RMS --> MOOD["mood"]:::dec
  RMS --> DIR["direction"]:::dec
  BANDS --> COLOUR["dominant colour"]:::dec
  ONSET --> BEATS["beat grid"]:::feat --> TEMPO["trailing tempo"]:::feat
  ONSET --> DRIVE["drive"]:::feat

  MOOD --> FAMILY["effect family"]:::dec
  MOOD -. peak .-> STROBE["colour strobe"]:::dec
  COLOUR --> FAMILY
  FAMILY --> MODE["mode number"]:::dec
  COLOUR --> MODE
  TEMPO --> SPEED["speed"]:::dec
  DRIVE --> SPEED

  MODE --> REC{{"reconciler"}}:::out
  BRIGHT --> REC
  SPEED --> REC
  STROBE --> REC
  DIR -.-> MODE
  REC --> BLE["BLE 9-byte frames"]:::out --> STRIP["💡 LED strip"]:::strip
`;

// step label -> where in the code it lives (shown as the legend under the graph)
const REFS: [string, string][] = [
  ["🎵 audio", "ytsource.download"],
  ["resample · STFT", "analysis.analyze · librosa.stft"],
  ["loudness", "librosa.feature.rms"],
  ["whitened bands", "analysis.analyze"],
  ["onset envelope", "librosa.onset.onset_strength"],
  ["brightness", "analysis.analyze → player.tick"],
  ["mood", "analysis._mood_track"],
  ["direction", "analysis._direction_track"],
  ["dominant colour", "analysis._color_track"],
  ["beat grid", "librosa.beat.beat_track"],
  ["trailing tempo", "analysis._trailing_tempo"],
  ["drive", "analysis.analyze (onset density)"],
  ["effect family", "planner.build_plan · modes.mood_family"],
  ["colour strobe", "planner.build_plan · player.tick"],
  ["mode number", "modes.resolve_mode"],
  ["speed", "player.tick (tempo + drive)"],
  ["reconciler", "player.tick (command budget)"],
  ["BLE frames", "protocol.py · controller.send"],
];

let configured = false;
let renderSeq = 0;

// Mermaid is loaded lazily (code-split). Render only once the container is visible
// (this page is mounted but display:none when inactive; a zero-size render collapses).
export default function PipelineFlow() {
  const box = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    let cancelled = false;
    let done = false;

    async function render() {
      if (done || cancelled || !el || el.offsetWidth === 0) return;
      done = true;
      try {
        const mermaid = (await import("mermaid")).default;
        if (!configured) {
          configured = true;
          mermaid.initialize({
            startOnLoad: false,
            securityLevel: "loose",
            theme: "base",
            themeVariables: { fontFamily: "ui-sans-serif, system-ui, sans-serif", fontSize: "12px", lineColor: "#3a4254", textColor: "#cdd2dc" },
            flowchart: { htmlLabels: false, curve: "basis", nodeSpacing: 26, rankSpacing: 42, padding: 6, useMaxWidth: true },
          });
        }
        const { svg } = await mermaid.render("flow-" + (renderSeq++), DEF);
        if (!cancelled && el) el.innerHTML = svg;
      } catch (e) {
        done = false;
        setErr(String(e));
      }
    }

    render();
    const ro = new ResizeObserver(() => render());
    ro.observe(el);
    return () => { cancelled = true; ro.disconnect(); };
  }, []);

  return (
    <div className="bg-panel2 border border-line rounded-xl p-3 flex flex-col gap-3">
      <div ref={box} className="mermaid-flow overflow-x-auto" />
      {err && <div className="text-[11px] text-off">diagram failed to render: {err}</div>}
      <div className="border-t border-line pt-2.5">
        <div className="text-[11px] text-mute mb-1.5">Where each step lives in the code</div>
        <div className="grid sm:grid-cols-2 gap-x-5 gap-y-1">
          {REFS.map(([step, where]) => (
            <div key={step} className="flex items-baseline gap-2 text-[11px]">
              <span className="text-ink shrink-0">{step}</span>
              <span className="flex-1 border-b border-dotted border-line2/60 translate-y-[-2px]" />
              <code className="font-mono text-[10.5px] text-mute shrink-0">{where}</code>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
