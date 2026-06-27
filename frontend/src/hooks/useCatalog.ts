import { useEffect, useMemo, useState } from "react";
import { get } from "@/api";
import type { FamilyInfo, ModeGroup } from "@/api";

// Loads the static mode catalog + family/colour metadata once.
export function useCatalog() {
  const [groups, setGroups] = useState<ModeGroup[]>([]);
  const [families, setFamilies] = useState<FamilyInfo[]>([]);
  const [colorHex, setColorHex] = useState<Record<string, string>>({});
  const [barColors, setBarColors] = useState<string[]>([]);
  const [barFreqs, setBarFreqs] = useState<number[]>([]);

  useEffect(() => {
    get<{ groups: ModeGroup[] }>("/api/modes").then((j) => setGroups(j.groups || []));
    get<any>("/api/families").then((j) => {
      setFamilies(j.families || []);
      setColorHex(j.color_hex || {});
      setBarColors(j.bar_colors || []);
      setBarFreqs(j.bar_freqs || []);
    });
  }, []);

  const num2name = useMemo(() => {
    const m: Record<number, string> = {};
    groups.forEach((g) => g.effects.forEach((e) => {
      (["fwd", "bwd", "open", "close", "single"] as const).forEach((k) => { if (e[k] != null) m[e[k]!] = e.name; });
    }));
    return m;
  }, [groups]);

  return { groups, families, colorHex, barColors, barFreqs, num2name };
}
