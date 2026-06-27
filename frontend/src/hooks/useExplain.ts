import { useCallback, useEffect, useState } from "react";
import { get } from "@/api";

export interface Param {
  value: number; min: number; max: number; step: number;
  reanalyse: boolean; group: string; label: string; desc: string;
}
export interface Explain {
  params: Record<string, Param>;
  mood_names: string[];
  mood_families: Record<string, string[]>;
  freq_colors: string[];
  color_hex: Record<string, string>;
  speed: { min: number; max: number; tempo_w: number; drive_w: number };
  dsp: { sr: number; n_fft: number; hop: number; nbars: number; fps: number };
  configs: string[];
}

// Shared algorithm-explainer state: the params, their live slider values, tuning
// (re-analyses for analysis params), and config save/load.
export function useExplain(onPlanChange: () => void) {
  const [data, setData] = useState<Explain | null>(null);
  const [vals, setVals] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const j = await get<Explain>("/api/explain");
    setData(j);
    setVals(Object.fromEntries(Object.entries(j.params).map(([k, p]) => [k, p.value])));
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const setVal = useCallback((k: string, v: number) => setVals((s) => ({ ...s, [k]: v })), []);

  const tune = useCallback(async (k: string) => {
    if (!data) return;
    const p = data.params[k];
    if (p.reanalyse) setBusy(true);
    await get(`/api/tune?name=${k}&value=${vals[k]}`);
    if (p.reanalyse) setBusy(false);
    onPlanChange();                       // runtime params (e.g. broadband threshold) reshape the plan too
  }, [data, vals, onPlanChange]);

  const loadConfig = useCallback(async (name: string) => {
    setBusy(true);
    await get("/api/config/load?name=" + encodeURIComponent(name));
    setBusy(false);
    await refresh(); onPlanChange();
  }, [refresh, onPlanChange]);

  const saveConfig = useCallback(async (name: string) => {
    if (!name.trim()) return;
    const j = await get<{ configs: string[] }>("/api/config/save?name=" + encodeURIComponent(name.trim()));
    setData((p) => (p ? { ...p, configs: j.configs } : p));
  }, []);

  return { data, vals, busy, setVal, tune, loadConfig, saveConfig };
}
export type UseExplain = ReturnType<typeof useExplain>;
