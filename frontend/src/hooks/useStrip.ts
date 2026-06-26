import { useCallback, useEffect, useState } from "react";
import { api, get } from "@/api";
import type { CmdStats } from "@/api";

// Connection + command-rate polling + the `act` helper (fires an API call and
// surfaces a ✓/✗ status message).
export function useStrip() {
  const [connected, setConnected] = useState(false);
  const [cmds, setCmds] = useState<CmdStats | null>(null);
  const [status, setStatus] = useState<{ msg: string; ok: boolean }>({ msg: "", ok: true });

  const act = useCallback(async (url: string) => {
    try {
      const j = await api(url);
      setStatus({ msg: j.ok ? "✓ " + (j.sent || "ok") : "✗ " + j.error, ok: !!j.ok });
      return j;
    } catch (e) {
      setStatus({ msg: "✗ " + e, ok: false });
    }
  }, []);

  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const st = await get<{ connected: boolean; cmds: CmdStats }>("/api/state");
        setConnected(st.connected); setCmds(st.cmds);
      } catch { setConnected(false); }
    }, 500);
    return () => clearInterval(id);
  }, []);

  return { act, status, connected, cmds };
}
