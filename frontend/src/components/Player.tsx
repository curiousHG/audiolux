import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import type { PlayerState, SearchResult } from "@/api";
import { fmtTime, get } from "@/api";
import { Search, Sparkles, Zap } from "lucide-react";
import { h2, btn, btnMini, cx } from "@/ui";

export interface PlayerHandle { pause: () => void; seek: (t: number) => void }

interface Props {
  active: boolean;                 // false while the mic engine owns the strip
  smart: boolean;
  onSmart: (on: boolean) => void;
  strobe: boolean;
  onStrobe: (on: boolean) => void;
  onTrackState: (s: PlayerState) => void;
  onPlayingChange: (playing: boolean) => void;
}

type LoadState = "idle" | "starting" | "downloading" | "analyzing" | "ready" | "error";

// Load the YouTube IFrame API once, shared across the app.
let ytPromise: Promise<any> | null = null;
function loadYT(): Promise<any> {
  const w = window as any;
  if (w.YT?.Player) return Promise.resolve(w.YT);
  if (ytPromise) return ytPromise;
  ytPromise = new Promise((resolve) => {
    const tag = document.createElement("script");
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);
    w.onYouTubeIframeAPIReady = () => resolve(w.YT);
  });
  return ytPromise;
}

const Player = forwardRef<PlayerHandle, Props>(function Player(
  { active, smart, onSmart, strobe, onStrobe, onTrackState, onPlayingChange }, ref) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [searching, setSearching] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [load, setLoad] = useState<LoadState>("idle");
  const [progress, setProgress] = useState(0);
  const [err, setErr] = useState("");
  const [videoId, setVideoId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);          // YT player ready
  const [analysisReady, setAnalysisReady] = useState(false);

  const yt = useRef<any>(null);
  const holder = useRef<HTMLDivElement>(null);
  const played = useRef(false);

  useImperativeHandle(ref, () => ({
    pause: () => yt.current?.pauseVideo?.(),
    seek: (t: number) => yt.current?.seekTo?.(t, true),
  }));

  async function search() {
    if (!q.trim()) return;
    setSearching(true);
    try {
      const j = await get<{ results: SearchResult[] }>("/api/yt/search?q=" + encodeURIComponent(q));
      setResults(j.results || []); setShowResults(true);
    } finally {
      setSearching(false);
    }
  }

  async function choose(r: SearchResult) {
    setActiveId(r.id); setShowResults(false); setErr(""); setLoad("starting"); setProgress(0);
    setAnalysisReady(false); played.current = false;
    yt.current?.pauseVideo?.();
    setVideoId(r.id);                          // cue the video (paused) — plays once ready
    // download + offline analysis on the backend; playback waits for it
    await get(`/api/yt/load?id=${r.id}&title=${encodeURIComponent(r.title)}&dur=${r.duration}`);
    const poll = async () => {
      const s = await get<any>("/api/yt/status?id=" + r.id);
      setLoad(s.state); setProgress(s.progress || 0);
      if (s.state === "error") setErr(s.error || "failed");
      else if (s.state === "ready") setAnalysisReady(true);
      else setTimeout(poll, 600);
    };
    poll();
  }

  // (re)point the YT player at the chosen video — CUE only (paused), don't autoplay
  useEffect(() => {
    if (!videoId) return;
    let cancelled = false;
    loadYT().then((YT) => {
      if (cancelled) return;
      if (yt.current?.cueVideoById) { yt.current.cueVideoById(videoId); return; }
      yt.current = new YT.Player(holder.current, {
        videoId,
        playerVars: { autoplay: 0, controls: 1, rel: 0, modestbranding: 1, playsinline: 1 },
        events: {
          onReady: () => setReady(true),
          onStateChange: (e: any) => onPlayingChange(e.data === YT.PlayerState.PLAYING),
        },
      });
    });
    return () => { cancelled = true; };
  }, [videoId, onPlayingChange]);

  // start playback only once BOTH the player and the offline analysis are ready
  useEffect(() => {
    if (ready && analysisReady && active && !played.current && yt.current?.playVideo) {
      played.current = true;
      yt.current.playVideo();
    }
  }, [ready, analysisReady, active]);

  // tick loop: report the video clock so the lights stay in sync
  useEffect(() => {
    if (!ready || !active) return;
    const id = setInterval(async () => {
      const p = yt.current;
      if (!p?.getCurrentTime) return;
      const t = p.getCurrentTime() || 0;
      const playing = p.getPlayerState?.() === (window as any).YT.PlayerState.PLAYING;
      const s = await get<PlayerState>(`/api/player/tick?t=${t.toFixed(2)}&playing=${playing ? 1 : 0}`);
      onTrackState(s);
    }, 120);
    return () => clearInterval(id);
  }, [ready, active, onTrackState]);

  return (
    <div>
      <h2 className={cx(h2, "flex items-center justify-between flex-wrap gap-2")}>
        <span>Music Player</span>
        <span className="flex gap-1.5">
          <button className={cx(btnMini, "flex items-center gap-1", smart && "!bg-on")}
                  title="Pick the effect family automatically from the music's character (calm/groove/drive/peak)"
                  onClick={() => onSmart(!smart)}><Sparkles size={12} /> Smart: {smart ? "ON" : "OFF"}</button>
          <button className={cx(btnMini, "flex items-center gap-1", strobe && "!bg-on")}
                  title="On peaks, flash a coloured strobe in the music's colour (Smart mode only)"
                  onClick={() => onStrobe(!strobe)}><Zap size={12} /> Strobe: {strobe ? "ON" : "OFF"}</button>
        </span>
      </h2>
      <div className="flex gap-2">
        <input className="flex-1 px-3 py-[11px] text-sm" placeholder="search a song on YouTube…" value={q}
               onChange={(e) => setQ(e.target.value)}
               onFocus={() => results.length && setShowResults(true)}
               onKeyDown={(e) => e.key === "Enter" && search()} />
        <button className={cx(btn, "!flex-none px-4 flex items-center gap-1.5")} onClick={search} disabled={searching}>
          <Search size={15} /> {searching ? "…" : "Search"}
        </button>
      </div>

      {showResults && results.length > 0 && (
        <div className="my-2.5 max-h-[230px] overflow-y-auto flex flex-col gap-1">
          {results.map((r) => (
            <div key={r.id}
                 className={cx("flex items-center gap-3 px-3 py-2 rounded-[10px] bg-panel border cursor-pointer transition-colors hover:bg-[#1a1f2c]",
                   r.id === activeId ? "border-accent" : "border-[#1c2230]")}
                 onClick={() => choose(r)}>
              <span className="flex-1 min-w-0 truncate text-[13px]">{r.title}{r.uploader && <span className="text-dim text-[11px]"> · {r.uploader}</span>}</span>
              <span className="text-mute text-xs tabular-nums">{fmtTime(r.duration)}</span>
            </div>
          ))}
        </div>
      )}

      {videoId && (
        <div className="mt-3">
          <div className="video-frame w-full max-w-[640px] aspect-video mx-auto rounded-xl overflow-hidden bg-black border border-line"><div ref={holder} /></div>
          <div className="text-xs text-mute mt-2 text-center">
            {load === "error" ? `✗ ${err}` :
              load === "ready" ? "✓ lights synced to this track" :
                load === "analyzing" ? "analysing audio (beat grid + light timeline)…" :
                  load === "downloading" ? `downloading audio for analysis… ${Math.round(progress * 100)}%` :
                    "preparing…"}
            {load !== "error" && load !== "ready" && (
              <div className="h-1.5 bg-line rounded mt-1.5 overflow-hidden max-w-[640px] mx-auto">
                <div className="h-full bg-accent transition-[width]" style={{ width: `${Math.round(progress * 100)}%` }} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
});

export default Player;
