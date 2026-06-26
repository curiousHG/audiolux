import { useState } from "react";
import { useStrip } from "@/hooks/useStrip";
import { useCatalog } from "@/hooks/useCatalog";
import { useMusic } from "@/hooks/useMusic";
import { useExplain } from "@/hooks/useExplain";
import Header, { type Page } from "@/components/Header";
import Player from "@/components/Player";
import Telemetry from "@/components/Telemetry";
import TrackTimeline from "@/components/TrackTimeline";
import CommandRate from "@/components/CommandRate";
import Tuning from "@/components/Tuning";
import ControlsPage from "@/components/ControlsPage";
import HowItWorks from "@/components/HowItWorks";
import Divider from "@/components/Divider";
import { usePersist, clamp } from "@/hooks/usePersist";

export default function App() {
  const { act, status, connected, cmds } = useStrip();
  const cat = useCatalog();
  const m = useMusic(act);
  const ex = useExplain(m.refreshPlan);
  const [page, setPage] = useState<Page>("player");
  const [powerOn, setPowerOn] = useState(true);
  const [tuningW, setTuningW] = usePersist("audiolux.tuningW", 360);   // draggable, saved
  const [timelineH, setTimelineH] = usePersist("audiolux.timelineH", 300);

  const onPower = (on: boolean) => { setPowerOn(on); act("/api/power?on=" + (on ? 1 : 0)); };

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header page={page} setPage={setPage} connected={connected} powerOn={powerOn} onPower={onPower} />

      <main className="flex-1 min-h-0 p-2">
        {/* PLAYER — fills the viewport, no scroll. Always mounted (audio + ticks keep
            running across pages); only hidden via CSS so the timeline resumes on return. */}
        <div className={page === "player" ? "h-full flex flex-col gap-1 min-h-0" : "hidden"}>
          {/* top: [ video + telemetry ] | drag | [ tuning ] */}
          <div className="flex-1 min-h-0 flex gap-1">
            <div className="flex-1 min-w-0 flex flex-col gap-2">
              <Player ref={m.playerRef} active={!m.micOn} smart={m.smart} onSmart={m.onSmart}
                      strobe={m.strobe} onStrobe={m.onStrobe}
                      onTrackState={m.onTrackState} onPlayingChange={m.onPlaying} />
              <Telemetry telem={m.telem} hist={m.hist.current} colorHex={cat.colorHex}
                         barColors={cat.barColors} num2name={cat.num2name} hasTrack={!!m.plan} />
            </div>
            <Divider axis="x" onResize={(d) => setTuningW((w) => clamp(w - d, 260, 680))} />
            <div className="shrink-0 min-h-0" style={{ width: tuningW }}>
              <Tuning ex={ex} />
            </div>
          </div>

          {/* drag | song timeline (resizable height) */}
          <Divider axis="y" onResize={(d) => setTimelineH((h) => clamp(h - d, 200, 640))} />
          <div className="shrink-0" style={{ height: timelineH }}>
            {m.plan ? (
              <TrackTimeline plan={m.plan} pos={m.telem?.pos || 0} colorHex={cat.colorHex} onSeek={m.seek} />
            ) : (
              <div className="h-full bg-panel border border-line rounded-xl flex items-center justify-center text-mute text-sm">
                Load a song to see its timeline
              </div>
            )}
          </div>

          <div className="shrink-0 text-[11px] truncate" style={{ color: status.ok ? "#5aa9ff" : "#e0667a" }}>{status.msg}</div>
        </div>

        {/* CONTROLS */}
        <div className={page === "controls" ? "h-full overflow-y-auto flex flex-col gap-3" : "hidden"}>
          <ControlsPage act={act} groups={cat.groups} families={cat.families}
                        micOn={m.micOn} onMicChange={m.setMicOn} />
          <CommandRate cmds={cmds} />
        </div>

        {/* HOW IT WORKS */}
        <div className={page === "how" ? "h-full overflow-y-auto" : "hidden"}>
          <HowItWorks ex={ex} />
        </div>
      </main>
    </div>
  );
}
