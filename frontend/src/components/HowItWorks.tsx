import Tex from "@/components/Tex";
import PipelineFlow from "@/components/PipelineFlow";
import type { Explain, UseExplain } from "@/hooks/useExplain";

// Each stage: how one musical feature maps to one light parameter. `prose` is the
// plain-English explanation (left column); GroupMath renders the formula (right).
const STAGES = [
  { key: "Loudness → Brightness", n: 1, sub: "louder music → brighter strip",
    file: "analysis.analyze · player.tick",
    prose: "The strip's brightness tracks how loud the music is. We measure each frame's RMS energy, convert it to decibels relative to the song's own loud level (its 95th-percentile RMS), then stretch that to the song's own loudness spread so it spans the full range — quiet sections really dim, loud ones hit 100% — even on a heavily-compressed track. The output is floored so it never goes fully dark." },
  { key: "Spectrum → Colour", n: 2, sub: "dominant frequency band → colour",
    file: "analysis._color_track",
    prose: "The colour comes from which part of the spectrum is most active right now. The 40 frequency bars are whitened — each divided by its own song-long average — so bass doesn't always win. They're pooled into 6 bands from low to high, and the loudest band picks the colour (red = bass … white = air)." },
  { key: "Energy → Mood", n: 3, sub: "energy + percussiveness → effect family",
    file: "analysis._mood_track · modes.mood_family",
    prose: "Every moment is labelled with a mood — calm, groove, drive or peak — from its loudness and how percussive it is (an HPSS harmonic/percussive split). The mood decides which family of effects plays, and the colour above decides the exact variant." },
  { key: "Tempo → Speed", n: 4, sub: "tempo baseline + live intensity → animation speed",
    file: "analysis (_trailing_tempo + drive) · player.tick",
    prose: "Animation speed. A song's tempo barely changes within it, so the trailing tempo (median time between recent beats, folded toward the global tempo) only sets a baseline and places the song across the full speed range. The live drive — onset intensity, stretched 0…1 per song — then supplies the moment-to-moment movement." },
  { key: "Build/Release → Direction", n: 5, sub: "rising vs falling energy → effect direction",
    file: "analysis._direction_track",
    prose: "Direction follows the shape of the energy. When loudness climbs above its own slow-moving average the effect runs forward (a build); when it drops below, the effect reverses (a release); otherwise it holds." },
] as const;

function GroupMath({ g, v, d }: { g: string; v: Record<string, number>; d: Explain }) {
  const cap = "text-[12px] text-mute leading-relaxed";
  if (g === "Loudness → Brightness") return (
    <>
      <Tex block tex={`\\ell=\\operatorname{clip}\\!\\left(\\frac{20\\log_{10}(\\mathrm{RMS}/P_{95})-(${v.db_floor})}{${Math.abs(v.db_floor)}},\\,0,\\,1\\right)`} />
      <Tex block tex={`\\mathrm{bright}=\\operatorname{clip}\\!\\left(\\frac{\\ell-\\ell_{5}}{\\ell_{95}-\\ell_{5}},\\,0,\\,1\\right)`} />
      <Tex block tex={`\\text{level}\\%=\\text{floor}+\\mathrm{bright}\\cdot(100-\\text{floor})`} />
      <p className={cap}><i>P₉₅</i> = the track's 95th-pct loudness (its “loud” reference); <i>ℓ₅..ℓ₉₅</i> = the song's own loudness spread, so brightness uses the full range per song.</p>
    </>
  );
  if (g === "Spectrum → Colour") return (
    <>
      <Tex block tex={`\\tilde b_i=\\frac{b_i}{\\overline{b_i}},\\qquad \\text{disp}_i=\\bigl(0.5\\,\\tilde b_i\\bigr)^{${v.spec_gamma}}`} />
      <Tex block tex={`c=\\operatorname*{arg\\,max}_{g}\\ \\sum_{i\\in g}\\tilde b_i\\,w_g,\\quad w_{\\text{WH}}=${v.white_deemph}`} />
      <p className={cap}><i>bᵢ</i> = mean |S| in log-bar <i>i</i>, <i>b̄ᵢ</i> its song-average (whitening). Bands <b className="text-ink">{d.freq_colors.join(" ")}</b> run bass→treble; the colour holds below <Tex tex={String(v.colour_silence)} /> brightness.</p>
    </>
  );
  if (g === "Energy → Mood") return (
    <>
      <Tex block tex={`p=\\frac{\\textstyle\\sum P}{\\textstyle\\sum H+\\sum P}`} />
      <Tex block tex={`\\text{mood}=\\begin{cases}\\text{peak}& e>${v.mood_peak_e}\\ \\wedge\\ p>${v.mood_peak_p}\\\\[2pt]\\text{drive}& e>${v.mood_drive_e}\\\\[2pt]\\text{groove}& e>${v.mood_groove_e}\\\\[2pt]\\text{calm}&\\text{otherwise}\\end{cases}`} />
      <div className="text-[12px] text-mute flex flex-col gap-0.5 mt-1">
        {d.mood_names.map((m, i) => (
          <span key={m}><b className="text-ink capitalize">{m}</b> → {(d.mood_families[String(i)] || []).slice(0, 3).join(", ")}</span>
        ))}
        <span className="text-dim">peak → software coloured strobe (flashes the live music colour and dark).</span>
      </div>
    </>
  );
  if (g === "Tempo → Speed") return (
    <>
      <Tex block tex={`\\tau=\\operatorname{clip}\\!\\left(\\tfrac{\\mathrm{BPM}-${v.speed_bpm_lo}}{${v.speed_span}},\\,0,\\,1\\right)`} />
      <Tex block tex={`v=${d.speed.min}+${d.speed.max - d.speed.min}\\cdot\\operatorname{clip}\\bigl(${d.speed.tempo_w}\\,\\tau+${d.speed.drive_w}\\,\\delta,\\,0,\\,1\\bigr)`} />
      <p className={cap}><i>τ</i> = trailing tempo (cross-song baseline), <i>δ</i> = live drive (within-song movement). Together they span the full {d.speed.min}–{d.speed.max} speed range.</p>
    </>
  );
  return (
    <>
      <Tex block tex={`\\bar b_t=\\operatorname{EMA}(b,\\,0.02)`} />
      <Tex block tex={`\\text{dir}=\\begin{cases}\\text{forward}& b_t>${v.dir_build}\\,\\bar b_t\\\\[2pt]\\text{backward}& b_t<${v.dir_release}\\,\\bar b_t\\\\[2pt]\\text{hold}&\\text{otherwise}\\end{cases}`} />
      <p className={cap}><i>b̄ₜ</i> is brightness smoothed with a slow exponential average.</p>
    </>
  );
}

function features(dsp: Explain["dsp"]): [string, string, string][] {
  return [
    ["STFT", `librosa.stft(n_fft=${dsp.n_fft}, hop=${dsp.hop}) @ ${dsp.sr} Hz`, `the magnitude spectrogram S — basis for everything, ~${dsp.fps} frames/s`],
    ["Loudness", "librosa.feature.rms(S)", "per-frame RMS energy → decibels vs the song's loud level"],
    ["Spectrum", `${dsp.nbars} log bars, 30 Hz–16 kHz, whitened`, "each bar ÷ its own song-average → 6 colour bands"],
    ["Percussiveness", "librosa.decompose.hpss(S)", "harmonic vs percussive energy → the mood"],
    ["Beats & tempo", "onset_strength → beat_track", "beat grid, global BPM, and a trailing local tempo"],
    ["Drive", "onset intensity, stretched per song", "how busy the moment feels → animation movement"],
    ["Broadband", "spectral flatness", "energy spread across all bands → white Strobe / Hop"],
  ];
}

export default function HowItWorks({ ex }: { ex: UseExplain }) {
  const { data: d, vals: v } = ex;
  if (!d) return null;

  return (
    <div className="w-full p-5 flex flex-col gap-5">
      <header className="flex flex-col gap-1.5">
        <h2 className="text-xl font-semibold">How it works</h2>
        <p className="text-[13px] text-mute leading-relaxed max-w-3xl">
          audiolux analyses the song offline into a per-frame timeline, then maps each musical feature to exactly
          one light parameter. Left: the pipeline graph and the raw features we pull from the audio. Right: how each
          feature drives the strip — with the live formula and the constants you can tune from the Player page.
        </p>
      </header>

      <div className="grid lg:grid-cols-2 gap-5 items-start">
        {/* LEFT: the pipeline graph + raw features */}
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <h3 className="text-[15px] font-semibold">The pipeline</h3>
            <PipelineFlow />
          </div>

          <section className="bg-panel2 border border-line rounded-xl p-4">
            <div className="flex items-baseline justify-between mb-3">
              <h3 className="text-[15px] font-semibold">Features extracted from the audio</h3>
              <span className="text-[11px] font-mono text-dim">analysis.analyze</span>
            </div>
            <div className="grid sm:grid-cols-2 gap-x-6 gap-y-3">
              {features(d.dsp).map(([fname, code, desc]) => (
                <div key={fname} className="flex flex-col gap-1">
                  <div className="text-[13px] font-medium text-ink">{fname}</div>
                  <code className="font-mono text-[11px] bg-panel rounded px-1.5 py-1 text-[#c7ccd8] self-start max-w-full overflow-x-auto">{code}</code>
                  <div className="text-[12px] text-mute leading-relaxed">{desc}</div>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* RIGHT: each mapping stage as a grid of cards (header, prose, formula stacked) */}
        <div className="flex flex-col gap-2">
          <h3 className="text-[15px] font-semibold">From feature to light</h3>
          <div className="grid sm:grid-cols-2 gap-3">
            {STAGES.map((s) => (
              <section key={s.key} className="bg-panel2 border border-line rounded-xl p-3.5 flex flex-col gap-2.5">
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-accent/15 text-accent text-[11px] font-semibold shrink-0">{s.n}</span>
                  <h4 className="text-[14px] font-semibold">{s.key}</h4>
                  <span className="text-[11px] text-mute basis-full">— {s.sub}</span>
                </div>
                <p className="text-[12.5px] text-[#c7ccd8] leading-relaxed">{s.prose}</p>
                <div className="bg-panel border border-line rounded-lg px-3 py-2.5 overflow-x-auto flex flex-col gap-1 mt-auto">
                  <GroupMath g={s.key} v={v} d={d} />
                </div>
                <span className="text-[10px] font-mono text-dim">{s.file}</span>
              </section>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
