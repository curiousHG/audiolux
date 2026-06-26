import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  CmdStats, FamilyInfo, ModeGroup, MusicState, PlayerState, Telemetry as TelemetryT,
} from "./api";
import { api, get } from "./api";
import { card, sectionTop, cx } from "./ui";
import PowerColor from "./components/PowerColor";
import Effects from "./components/Effects";
import MusicEngine from "./components/MusicEngine";
import Player, { type PlayerHandle } from "./components/Player";
import Telemetry, { type HistPoint } from "./components/Telemetry";
import Soundboard from "./components/Soundboard";
import CommandRate from "./components/CommandRate";

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

export default function App() {
  const [connected, setConnected] = useState(false);
  const [cmds, setCmds] = useState<CmdStats | null>(null);
  const [status, setStatus] = useState<{ msg: string; ok: boolean }>({ msg: "", ok: true });

  const [groups, setGroups] = useState<ModeGroup[]>([]);
  const [families, setFamilies] = useState<FamilyInfo[]>([]);
  const [colorHex, setColorHex] = useState<Record<string, string>>({});
  const [barColors, setBarColors] = useState<string[]>([]);

  const [micOn, setMicOn] = useState(false);
  const [smart, setSmart] = useState(false);
  const [strobe, setStrobe] = useState(true);
  const [telem, setTelem] = useState<TelemetryT | null>(null);
  const hist = useRef<HistPoint[]>([]);
  const playerRef = useRef<PlayerHandle>(null);

  const act = useCallback(async (url: string) => {
    try {
      const j = await api(url);
      setStatus({ msg: j.ok ? "✓ " + (j.sent || "ok") : "✗ " + j.error, ok: !!j.ok });
      return j;
    } catch (e) {
      setStatus({ msg: "✗ " + e, ok: false });
    }
  }, []);

  const pushTelem = useCallback((t: TelemetryT) => {
    setTelem(t);
    // colour history shows what the MUSIC suggests; the readout dot shows the actual light colour
    hist.current.push({ level: t.level, bright: t.brightness / 100, color: t.musicColor || t.color, centroid: t.centroid });
    if (hist.current.length > HIST_MAX) hist.current.shift();
  }, []);

  // load static catalogs once
  useEffect(() => {
    get<{ groups: ModeGroup[] }>("/api/modes").then((j) => setGroups(j.groups || []));
    get<any>("/api/families").then((j) => {
      setFamilies(j.families || []);
      setColorHex(j.color_hex || {});
      setBarColors(j.bar_colors || []);
    });
  }, []);

  // connection + command-rate poll
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const st = await get<{ connected: boolean; cmds: CmdStats }>("/api/state");
        setConnected(st.connected); setCmds(st.cmds);
      } catch { setConnected(false); }
    }, 500);
    return () => clearInterval(id);
  }, []);

  // mic engine: start/stop + telemetry poll
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

  const num2name = useMemo(() => {
    const m: Record<number, string> = {};
    groups.forEach((g) => g.effects.forEach((e) => {
      (["fwd", "bwd", "open", "close", "single"] as const).forEach((k) => { if (e[k] != null) m[e[k]!] = e.name; });
    }));
    return m;
  }, [groups]);

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

  return (
    <div className={card}>
      <h1 className="text-lg m-0 mb-1 tracking-[.3px]">
        audiolux
        <span className={cx("text-[11px] px-2.5 py-0.5 rounded-full align-middle ml-1.5",
          connected ? "bg-[#163a2a] text-[#57d090]" : "bg-[#3a1820] text-[#e0667a]")}>
          {connected ? "connected" : "not connected"}
        </span>
      </h1>
      <div className="text-mute text-xs mb-4">strip: LEDDMX-03-1821 · music-reactive LED control</div>

      <Player ref={playerRef} active={!micOn} smart={smart} onSmart={onSmart}
              strobe={strobe} onStrobe={onStrobe}
              onTrackState={onTrackState} onPlayingChange={onPlaying} />

      {telem && (
        <Telemetry telem={telem} hist={hist.current} colorHex={colorHex}
                   barColors={barColors} num2name={num2name} />
      )}

      <div className={cx(sectionTop, "grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-[26px] items-start")}>
        <PowerColor act={act} />
        <Effects act={act} groups={groups} />
        <MusicEngine act={act} families={families} micOn={micOn} onMicChange={setMicOn} />
      </div>

      <Soundboard act={act} />
      <CommandRate cmds={cmds} />

      <div className="mt-[18px] pt-2.5 text-xs min-h-4 border-t border-line"
           style={{ color: status.ok ? "#5aa9ff" : "#e0667a" }}>{status.msg}</div>
    </div>
  );
}
