import { useCallback, useEffect, useRef, useState } from "react";
import { get } from "../api";
import type { MusicState, PlayerState, Telemetry as TelemetryT } from "../api";
import type { HistPoint } from "../components/Telemetry";
import type { PlayerHandle } from "../components/Player";

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
    direction: s.direction, mood: s.mood, spectrum: s.spectrum,
  };
}

// Owns the live light source (mic engine vs track player), the smart/strobe
// toggles, and the rolling telemetry the dashboard renders.
export function useMusic(act: (u: string) => void) {
  const [micOn, setMicOn] = useState(false);
  const [smart, setSmart] = useState(false);
  const [strobe, setStrobe] = useState(true);
  const [telem, setTelem] = useState<TelemetryT | null>(null);
  const hist = useRef<HistPoint[]>([]);
  const playerRef = useRef<PlayerHandle>(null);

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
    if (s.loaded) pushTelem(playerTelem(s));
  }, [pushTelem]);
  const onSmart = useCallback((on: boolean) => {
    setSmart(on); act("/api/music/config?auto_family=" + on);
  }, [act]);
  const onStrobe = useCallback((on: boolean) => {
    setStrobe(on); act("/api/music/config?peak_strobe=" + on);
  }, [act]);

  return { micOn, setMicOn, smart, onSmart, strobe, onStrobe, telem, hist, playerRef, onPlaying, onTrackState };
}
