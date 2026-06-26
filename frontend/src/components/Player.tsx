import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import type { PlayerState, SearchResult } from "../api";
import { fmtTime, get } from "../api";

export interface PlayerHandle { pause: () => void }

interface Props {
  active: boolean;                 // false while the mic engine owns the strip
  onTrackState: (s: PlayerState) => void;
  onPlayingChange: (playing: boolean) => void;
  onAnalyser: (a: AnalyserNode | null) => void;
}

type LoadState = "idle" | "starting" | "downloading" | "analyzing" | "ready" | "error";

const Player = forwardRef<PlayerHandle, Props>(function Player(
  { active, onTrackState, onPlayingChange, onAnalyser }, ref) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [load, setLoad] = useState<LoadState>("idle");
  const [progress, setProgress] = useState(0);
  const [err, setErr] = useState("");
  const [track, setTrack] = useState<SearchResult | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [pos, setPos] = useState(0);
  const [dur, setDur] = useState(0);

  const audio = useRef<HTMLAudioElement>(null);
  const wired = useRef(false);   // WebAudio graph built once per element

  useImperativeHandle(ref, () => ({ pause: () => audio.current?.pause() }));

  async function search() {
    if (!q.trim()) return;
    setSearching(true);
    try {
      const j = await get<{ results: SearchResult[] }>("/api/yt/search?q=" + encodeURIComponent(q));
      setResults(j.results || []);
    } finally {
      setSearching(false);
    }
  }

  async function choose(r: SearchResult) {
    setActiveId(r.id); setTrack(r); setErr(""); setLoad("starting"); setProgress(0);
    await get(`/api/yt/load?id=${r.id}&title=${encodeURIComponent(r.title)}&dur=${r.duration}`);
    // poll until ready
    const poll = async () => {
      const s = await get<any>("/api/yt/status?id=" + r.id);
      setLoad(s.state); setProgress(s.progress || 0);
      if (s.state === "ready") { setAudioUrl(s.audio_url + "?t=" + r.id); }
      else if (s.state === "error") { setErr(s.error || "failed"); }
      else { setTimeout(poll, 600); }
    };
    poll();
  }

  // build the WebAudio analyser graph the first time the element plays
  function wire() {
    if (wired.current || !audio.current) return;
    wired.current = true;
    const Ctx = window.AudioContext || (window as any).webkitAudioContext;
    const ctx = new Ctx();
    const src = ctx.createMediaElementSource(audio.current);
    const an = ctx.createAnalyser();
    an.fftSize = 2048; an.smoothingTimeConstant = 0.7;
    src.connect(an); an.connect(ctx.destination);
    if (ctx.state === "suspended") ctx.resume();
    onAnalyser(an);
  }

  // backend tick loop: report the audio clock so the lights stay in sync
  useEffect(() => {
    if (!audioUrl || !active) return;
    const id = setInterval(async () => {
      const a = audio.current;
      if (!a) return;
      const s = await get<PlayerState>(`/api/player/tick?t=${a.currentTime.toFixed(2)}&playing=${a.paused ? 0 : 1}`);
      onTrackState(s);
    }, 120);
    return () => clearInterval(id);
  }, [audioUrl, active, onTrackState]);

  function togglePlay() {
    const a = audio.current; if (!a) return;
    if (a.paused) { wire(); a.play().catch(() => {}); } else a.pause();
  }

  return (
    <div className="player">
      <h2>🎬 Music Player <span className="boardsub">— search YouTube, play it, lights follow the track</span></h2>
      <div className="searchbar">
        <input placeholder="search a song…" value={q}
               onChange={(e) => setQ(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && search()} />
        <button onClick={search} disabled={searching}>{searching ? "…" : "Search"}</button>
      </div>

      {results.length > 0 && (
        <div className="results">
          {results.map((r) => (
            <div key={r.id} className={"result" + (r.id === activeId ? " active" : "")} onClick={() => choose(r)}>
              <span className="rtitle">{r.title}{r.uploader && <span className="rup"> · {r.uploader}</span>}</span>
              <span className="rdur">{fmtTime(r.duration)}</span>
            </div>
          ))}
        </div>
      )}

      {track && load !== "ready" && load !== "idle" && (
        <div className="loadnote">
          {load === "error" ? `✗ ${err}` :
            load === "analyzing" ? "analysing audio (beat grid + light timeline)…" :
              load === "downloading" ? `downloading… ${Math.round(progress * 100)}%` : "preparing…"}
          {load !== "error" && <div className="progress"><div style={{ width: `${Math.round(progress * 100)}%` }} /></div>}
        </div>
      )}

      {audioUrl && (
        <div className="nowbar">
          <button className="play" onClick={togglePlay}>{playing ? "⏸" : "▶"}</button>
          <div className="nowmeta">
            <div className="nowtitle">{track?.title}</div>
            <div className="seek">
              <span className="t">{fmtTime(pos)}</span>
              <input type="range" min={0} max={dur || 0} step={0.1} value={pos}
                     onChange={(e) => { if (audio.current) audio.current.currentTime = +e.target.value; setPos(+e.target.value); }} />
              <span className="t">{fmtTime(dur)}</span>
            </div>
          </div>
          <audio ref={audio} src={audioUrl}
                 onPlay={() => { wire(); setPlaying(true); onPlayingChange(true); }}
                 onPause={() => { setPlaying(false); onPlayingChange(false); }}
                 onTimeUpdate={(e) => setPos((e.target as HTMLAudioElement).currentTime)}
                 onLoadedMetadata={(e) => setDur((e.target as HTMLAudioElement).duration)}
                 onEnded={() => { setPlaying(false); onPlayingChange(false); }} />
        </div>
      )}
    </div>
  );
});

export default Player;
