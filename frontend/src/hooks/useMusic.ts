import { useCallback, useEffect, useRef, useState } from "react";
import { get } from "@/api";
import type { MusicState, Plan, PlayerState, Telemetry as TelemetryT } from "@/api";
import type { HistPoint } from "@/components/Telemetry";
import type { PlayerHandle } from "@/components/Player";

const HIST_MAX = 240;

function musicTelem(s: MusicState): TelemetryT {
  return {
    bpm: s.bpm, beat_flash: s.beat_flash, brightness: s.brightness, level: s.loudness,
    centroid: s.centroid, color: s.color, musicColor: s.music_color, family: s.family, mode: s.mode,
    direction: s.direction, C: s.C, spectrum: s.spectrum,
  };
}
function playerTelem(s: PlayerState): TelemetryT {
  return {
    bpm: s.bpm, beat_flash: s.beat_flash, brightness: s.brightness, level: s.brightness / 100,
    centroid: s.centroid, color: s.color, musicColor: s.music_color, family: s.family, mode: s.mode,
    direction: s.direction, mood: s.mood, spectrum: s.spectrum, pos: s.pos,
  };
}

// Owns the live light source (mic engine vs track player), the smart/strobe
// toggles, and the rolling telemetry the dashboard renders.
export function useMusic(act: (u: string) => void) {
  const [micOn, setMicOn] = useState(false);
  const [smart, setSmart] = useState(true);     // Smart on by default
  const [strobe, setStrobe] = useState(true);
  const [telem, setTelem] = useState<TelemetryT | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [planNonce, setPlanNonce] = useState(0);
  const hist = useRef<HistPoint[]>([]);
  const playerRef = useRef<PlayerHandle>(null);

  const seek = useCallback((t: number) => playerRef.current?.seek(t), []);

  const pushTelem = useCallback((t: TelemetryT) => {
    setTelem(t);
    // colour history shows what the MUSIC suggests; the readout dot shows the actual light colour
    hist.current.push({ level: t.level, bright: t.brightness / 100, color: t.musicColor || t.color, centroid: t.centroid });
    if (hist.current.length > HIST_MAX) hist.current.shift();
  }, []);

  useEffect(() => {
    if (!micOn) return;
    playerRef.current?.pause();
    act("/api/music/start");
    hist.current = [];
    const id = setInterval(async () => {
      try { pushTelem(musicTelem(await get<MusicState>("/api/music/state"))); } catch { /* ignore */ }
    }, 120);
    return () => {
      clearInterval(id);
      act("/api/music/stop");
      setTelem(null); hist.current = [];
    };
  }, [micOn, act, pushTelem]);

  const onPlaying = useCallback((playing: boolean) => {
    if (playing) setMicOn(false);   // track takes over from the mic
  }, []);
  const onTrackState = useCallback((s: PlayerState) => {
    setLoaded(s.loaded);
    if (s.loaded) pushTelem(playerTelem(s));
  }, [pushTelem]);
  const onSmart = useCallback((on: boolean) => {
    setSmart(on); act("/api/music/config?auto_family=" + on); setPlanNonce((n) => n + 1);
  }, [act]);
  const onStrobe = useCallback((on: boolean) => {
    setStrobe(on); act("/api/music/config?peak_strobe=" + on); setPlanNonce((n) => n + 1);
  }, [act]);

  // fetch the precomputed plan when a track is loaded; refresh on config changes
  // (planNonce) and poll slowly to catch drawer tweaks (families / beats-per-switch)
  useEffect(() => {
    if (!loaded) { setPlan(null); return; }
    let sig = "";
    const fetchPlan = async () => {
      try {
        const p = await get<Plan>("/api/player/plan");
        if (!p.loaded) return;
        const s = `${p.segments.length}|${p.families.join()}|${p.segments[0]?.mode}|${p.bpm}|${p.bright_floor}|${p.dir_marks.length}`;
        if (s !== sig) { sig = s; setPlan(p); }
      } catch { /* ignore */ }
    };
    fetchPlan();
    const id = setInterval(fetchPlan, 2000);
    return () => clearInterval(id);
  }, [loaded, planNonce]);

  const refreshPlan = useCallback(() => setPlanNonce((n) => n + 1), []);

  return { micOn, setMicOn, smart, onSmart, strobe, onStrobe, telem, plan, seek, refreshPlan, hist, playerRef, onPlaying, onTrackState };
}
