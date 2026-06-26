import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import type { PlayerState, SearchResult } from "../api";
import { fmtTime, get } from "../api";

export interface PlayerHandle { pause: () => void }

interface Props {
  active: boolean;                 // false while the mic engine owns the strip
  smart: boolean;
  onSmart: (on: boolean) => void;
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
  { active, smart, onSmart, onTrackState, onPlayingChange }, ref) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [load, setLoad] = useState<LoadState>("idle");
  const [progress, setProgress] = useState(0);
  const [err, setErr] = useState("");
  const [videoId, setVideoId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);   // YT player ready

  const yt = useRef<any>(null);
  const holder = useRef<HTMLDivElement>(null);

  useImperativeHandle(ref, () => ({ pause: () => yt.current?.pauseVideo?.() }));

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
    setActiveId(r.id); setErr(""); setLoad("starting"); setProgress(0);
    setVideoId(r.id);                          // video starts immediately
    // kick off download + offline analysis on the backend (lights engage once ready)
    await get(`/api/yt/load?id=${r.id}&title=${encodeURIComponent(r.title)}&dur=${r.duration}`);
    const poll = async () => {
      const s = await get<any>("/api/yt/status?id=" + r.id);
      setLoad(s.state); setProgress(s.progress || 0);
      if (s.state === "error") setErr(s.error || "failed");
      else if (s.state !== "ready") setTimeout(poll, 600);
    };
    poll();
  }

  // (re)point the YT player at the chosen video
  useEffect(() => {
    if (!videoId) return;
    let cancelled = false;
    loadYT().then((YT) => {
      if (cancelled) return;
      if (yt.current?.loadVideoById) { yt.current.loadVideoById(videoId); return; }
      yt.current = new YT.Player(holder.current, {
        videoId,
        playerVars: { autoplay: 1, controls: 1, rel: 0, modestbranding: 1, playsinline: 1 },
        events: {
          onReady: () => setReady(true),
          onStateChange: (e: any) => {
            const playing = e.data === YT.PlayerState.PLAYING;
            onPlayingChange(playing);
          },
        },
      });
    });
    return () => { cancelled = true; };
  }, [videoId, onPlayingChange]);

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
    <div className="player">
      <h2>🎬 Music Player
        <button className={"mini" + (smart ? " on" : "")} style={{ float: "right" }}
                title="Pick the effect family automatically from the music's character (calm/groove/drive/peak)"
                onClick={() => onSmart(!smart)}>🧠 Smart mode: {smart ? "ON" : "OFF"}</button>
      </h2>
      <div className="searchbar">
        <input placeholder="search a song on YouTube…" value={q}
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

      {videoId && (
        <div className="videowrap">
          <div className="video"><div ref={holder} /></div>
          <div className="loadnote">
            {load === "error" ? `✗ ${err}` :
              load === "ready" ? "✓ lights synced to this track" :
                load === "analyzing" ? "analysing audio (beat grid + light timeline)…" :
                  load === "downloading" ? `downloading audio for analysis… ${Math.round(progress * 100)}%` :
                    "preparing…"}
            {load !== "error" && load !== "ready" && <div className="progress"><div style={{ width: `${Math.round(progress * 100)}%` }} /></div>}
          </div>
        </div>
      )}
    </div>
  );
});

export default Player;
