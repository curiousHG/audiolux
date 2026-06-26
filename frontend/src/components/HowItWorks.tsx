import Tex from "@/components/Tex";
import type { Explain, UseExplain } from "@/hooks/useExplain";

const GROUPS = ["Loudness → Brightness", "Spectrum → Colour", "Energy → Mood", "Tempo → Speed", "Build/Release → Direction"];
const FILES: Record<string, string> = {
  "Loudness → Brightness": "analysis.analyze · player.tick",
  "Spectrum → Colour": "analysis._color_track",
  "Energy → Mood": "analysis._mood_track · modes.mood_family",
  "Tempo → Speed": "analysis (beat_track / tempo) · player.tick",
  "Build/Release → Direction": "analysis._direction_track",
};

function features(dsp: Explain["dsp"]): [string, string, string][] {
  return [
    ["STFT", `librosa.stft(y, n_fft=${dsp.n_fft}, hop=${dsp.hop}) @ ${dsp.sr} Hz`, `magnitude spectrogram S — basis for everything, ~${dsp.fps} frames/s`],
    ["Loudness", "librosa.feature.rms(S)", "per-frame RMS → dB vs the song's 95th-pct level"],
    ["Spectrum", `${dsp.nbars} log bars 30 Hz–16 kHz (mean |S|), ÷ each bar's song-average`, "whitened bars → 6 colour groups"],
    ["Percussiveness", "librosa.decompose.hpss(S)", "harmonic/percussive split → p = ΣP / (ΣH + ΣP)"],
    ["Beats & tempo", "onset_strength → beat_track / feature.tempo(aggregate=None)", "beat grid + global BPM + local BPM curve"],
    ["Spectral centroid", "librosa.feature.spectral_centroid(S)", "the 'brightness' of the timbre (telemetry line)"],
    ["Build/release", "slow EMA of brightness (α = 0.02)", "brightness vs its slow average → direction"],
  ];
}

function GroupMath({ g, v, d }: { g: string; v: Record<string, number>; d: Explain }) {
  if (g === "Loudness → Brightness") return (
    <>
      <Tex block tex={`\\mathrm{dB}=20\\,\\log_{10}\\!\\frac{\\mathrm{RMS}}{P_{95}}`} />
      <Tex block tex={`\\mathrm{bright}=\\operatorname{clip}\\!\\left(\\frac{\\mathrm{dB}-(${v.db_floor})}{${Math.abs(v.db_floor)}},\\,0,\\,1\\right)`} />
      <Tex block tex={`\\text{level}\\%=\\text{floor}+\\mathrm{bright}\\cdot(100-\\text{floor})`} />
      <p className="text-[11px] text-mute">RMS of the FFT magnitude; <i>P₉₅</i> = the track's 95th-percentile loudness (its "loud" level).</p>
    </>
  );
  if (g === "Spectrum → Colour") return (
    <>
      <Tex block tex={`\\tilde b_i=\\frac{b_i}{\\overline{b_i}},\\qquad \\text{disp}_i=\\bigl(0.5\\,\\tilde b_i\\bigr)^{${v.spec_gamma}}`} />
      <Tex block tex={`c=\\operatorname*{arg\\,max}_{g}\\ \\sum_{i\\in g}\\tilde b_i\\,w_g,\\quad w_{\\text{WH}}=${v.white_deemph}`} />
      <p className="text-[11px] text-mute"><i>bᵢ</i> = mean |S| in log-bar <i>i</i>; <i>b̄ᵢ</i> its song-average (whitening). Groups <b>{d.freq_colors.join(" ")}</b> bass→treble; holds below <Tex tex={String(v.colour_silence)} /> brightness.</p>
    </>
  );
  if (g === "Energy → Mood") return (
    <>
      <Tex block tex={`p=\\frac{\\textstyle\\sum P}{\\textstyle\\sum H+\\sum P}\\ \\ (\\text{HPSS percussive fraction})`} />
      <Tex block tex={`\\text{mood}=\\begin{cases}\\text{peak}& e>${v.mood_peak_e}\\ \\wedge\\ p>${v.mood_peak_p}\\\\[2pt]\\text{drive}& e>${v.mood_drive_e}\\\\[2pt]\\text{groove}& e>${v.mood_groove_e}\\\\[2pt]\\text{calm}&\\text{otherwise}\\end{cases}`} />
      <div className="text-[11px] text-mute flex flex-wrap gap-x-4 gap-y-0.5">
        {d.mood_names.map((m, i) => (
          <span key={m}><b className="text-ink capitalize">{m}</b> → {(d.mood_families[String(i)] || []).slice(0, 3).join(", ")}</span>
        ))}
      </div>
      <p className="text-[11px] text-dim">peak ⇒ coloured strobe; else the family that can render the colour → mode via <code>resolve_mode</code>.</p>
    </>
  );
  if (g === "Tempo → Speed") return (
    <>
      <Tex block tex={`v=\\operatorname{clip}\\!\\left(25+\\frac{\\mathrm{BPM}-${v.speed_bpm_lo}}{${v.speed_span}}\\cdot 75,\\ ${d.speed.min},\\ ${d.speed.max}\\right)`} />
      <p className="text-[11px] text-mute">Beats from beat-tracking; the family switches every <i>N</i> beats; BPM is the local (time-varying) tempo.</p>
    </>
  );
  return (
    <>
      <Tex block tex={`\\bar b_t=\\operatorname{EMA}(b,\\,0.02)`} />
      <Tex block tex={`\\text{dir}=\\begin{cases}\\text{forward}& b_t>${v.dir_build}\\,\\bar b_t\\\\[2pt]\\text{backward}& b_t<${v.dir_release}\\,\\bar b_t\\\\[2pt]\\text{hold}&\\text{otherwise}\\end{cases}`} />
      <p className="text-[11px] text-mute">A rising envelope runs the effect forward; a falling one runs it backward.</p>
    </>
  );
}

export default function HowItWorks({ ex }: { ex: UseExplain }) {
  const { data: d, vals: v } = ex;
  if (!d) return null;
  return (
    <div className="mt-3 bg-panel border border-line rounded-xl p-4 flex flex-col gap-4">
      <div>
        <h2 className="text-[13px] font-semibold">How it works</h2>
        <p className="text-[11px] text-dim">The full pipeline — features computed from the audio, then mapped to each light parameter. Tune the constants from the panel next to the video.</p>
      </div>

      {/* flow diagram */}
      <div className="flex items-center gap-1.5 text-[11px]">
        {[["🎵 Audio → FFT", []], ["Features", ["RMS loudness", "whitened spectrum", "HPSS percussive", "onset / beats"]],
          ["Decisions", ["→ brightness", "→ colour", "→ mood → family", "→ speed", "→ direction"]],
          ["🎚 Mode", ["family + colour", "→ mode #", "→ 💡 strip"]]].map(([title, lines], i, arr) => (
          <div key={title as string} className="contents">
            <div className="flex-1 min-w-0 bg-panel2 border border-line rounded-lg px-2.5 py-2 text-center">
              <div className="text-[11px] font-semibold text-accent">{title as string}</div>
              {(lines as string[]).length > 0 && <div className="text-[10px] text-mute mt-1 leading-snug">{(lines as string[]).map((l) => <div key={l}>{l}</div>)}</div>}
            </div>
            {i < arr.length - 1 && <span className="text-dim shrink-0">→</span>}
          </div>
        ))}
      </div>

      {/* features */}
      <div className="bg-panel2 border border-line rounded-lg p-3">
        <div className="text-xs font-semibold text-[#c7ccd8] mb-2">
          Features <span className="text-mute font-normal">— how they're computed from the audio</span>
          <span className="text-[10px] text-dim font-mono ml-2">analysis.analyze</span>
        </div>
        <div className="grid md:grid-cols-2 gap-x-6 gap-y-2">
          {features(d.dsp).map(([fname, code, desc]) => (
            <div key={fname} className="text-xs">
              <span className="text-ink font-medium">{fname}</span>
              <code className="font-mono text-[11px] bg-panel rounded px-1.5 py-0.5 text-[#c7ccd8] ml-1.5">{code}</code>
              <div className="text-mute mt-0.5">{desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* per-group maths */}
      <div className="grid md:grid-cols-2 gap-3">
        {GROUPS.map((g) => (
          <div key={g} className="bg-panel2 border border-line rounded-lg p-3">
            <div className="flex items-baseline justify-between mb-1.5">
              <span className="text-xs font-semibold text-[#c7ccd8]">{g}</span>
              <span className="text-[10px] text-dim font-mono">{FILES[g]}</span>
            </div>
            <GroupMath g={g} v={v} d={d} />
          </div>
        ))}
      </div>
    </div>
  );
}
