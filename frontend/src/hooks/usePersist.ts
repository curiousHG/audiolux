import { useEffect, useState } from "react";

// A number persisted to localStorage (browser cache), so resized sizes stick.
export function usePersist(key: string, initial: number) {
  const [v, setV] = useState<number>(() => {
    const s = localStorage.getItem(key);
    const n = s == null ? NaN : parseFloat(s);
    return Number.isFinite(n) ? n : initial;
  });
  useEffect(() => { localStorage.setItem(key, String(v)); }, [key, v]);
  return [v, setV] as const;
}

export const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
