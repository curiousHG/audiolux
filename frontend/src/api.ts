// Thin fetch helpers + shared types for the LEDDMX backend API.

export async function api(url: string): Promise<any> {
  const r = await fetch(url);
  return r.json();
}

export async function get<T = any>(url: string): Promise<T> {
  const r = await fetch(url);
  return r.json() as Promise<T>;
}

// ---- types ----
export interface CmdStats {
  total: number;
  dropped: number;
  rate: number;
  hist: number[];
  bucket: number;
  max_rate: number;
}

export interface MusicCfg {
  react_bright: boolean;
  react_speed: boolean;
  switch_modes: boolean;
  use_direction: boolean;
  sensitivity: number;
  beats_per_switch: number;
  bright_floor: number;
  smooth: number;
}

export interface MusicState {
  on: boolean;
  bpm: number;
  beats: number;
  beat_flash: number;
  loudness: number;
  brightness: number;
  speed: number;
  centroid: number;
  spectrum: number[];
  mode: number | null;
  family: string | null;
  color: string;
  music_color: string;
  direction: "fwd" | "bwd";
  C: number;
  active_families: string[];
  cfg: MusicCfg;
}

export interface PlayerState {
  loaded: boolean;
  playing: boolean;
  pos: number;
  track: { id: string; title: string; uploader?: string; duration: number } | null;
  duration: number;
  bpm: number;
  beats: number;
  beat_flash: number;
  brightness: number;
  speed: number;
  centroid: number;
  color: string;
  music_color: string;
  family: string | null;
  mode: number | null;
  direction: "fwd" | "bwd";
  mood: string | null;
  spectrum: number[];
  loading: boolean;
}

export interface SearchResult {
  id: string;
  title: string;
  uploader: string;
  duration: number;
}

export interface FamilyInfo {
  family: string;
  colors: string[];
  single: number;
  color_react: boolean;
}

export interface EffectMode {
  name: string;
  single?: number;
  fwd?: number;
  bwd?: number;
  open?: number;
  close?: number;
}

export interface ModeGroup {
  family: string;
  effects: EffectMode[];
}

// A normalised telemetry shape both the mic engine and the player can fill.
export interface Telemetry {
  bpm: number;
  beat_flash: number;
  brightness: number; // 0..100
  level: number; // 0..1 — loudness (mic) or brightness/100 (player)
  centroid: number;
  color: string;
  musicColor: string;
  family: string | null;
  mode: number | null;
  direction: "fwd" | "bwd";
  C?: number;
  mood?: string | null;
  spectrum?: number[];
  pos?: number;
}

export interface PlanSegment {
  t0: number;
  t1: number;
  kind: "mode" | "strobe";
  family: string;
  mode: number | null;
  color: string;
  mood: number;
}

export interface Plan {
  loaded: boolean;
  duration: number;
  bpm: number;
  segments: PlanSegment[];
  families: string[];
  sig_t: number[];
  level: number[];
  scolor: string[];
}

export function fmtTime(s: number): string {
  if (!s || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}
