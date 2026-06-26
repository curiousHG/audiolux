import { useState } from "react";
import { card, cx } from "@/ui";
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

export default function App() {
  const { act, status, connected, cmds } = useStrip();
  const cat = useCatalog();
  const m = useMusic(act);
  const ex = useExplain(m.refreshPlan);
  const [page, setPage] = useState<Page>("player");
  const [powerOn, setPowerOn] = useState(true);

  const onPower = (on: boolean) => { setPowerOn(on); act("/api/power?on=" + (on ? 1 : 0)); };

  return (
    <>
      <Header page={page} setPage={setPage} connected={connected} powerOn={powerOn} onPower={onPower} />

      <main className="px-3 py-3">
        {/* PLAYER — always mounted (YouTube audio + ticks keep running across pages);
            only hidden via CSS when on another page, so the timeline resumes on return */}
        <div className={page === "player" ? "" : "hidden"}>
          <div className={card}>
            <div className="grid lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)] gap-4 items-stretch">
              <div className="flex flex-col gap-4 min-w-0">
                <Player ref={m.playerRef} active={!m.micOn} smart={m.smart} onSmart={m.onSmart}
                        strobe={m.strobe} onStrobe={m.onStrobe}
                        onTrackState={m.onTrackState} onPlayingChange={m.onPlaying} />
                <Telemetry telem={m.telem} hist={m.hist.current} colorHex={cat.colorHex}
                           barColors={cat.barColors} num2name={cat.num2name} hasTrack={!!m.plan} />
              </div>
              <Tuning ex={ex} />
            </div>

            <div className="mt-4">
              {m.plan ? (
                <TrackTimeline plan={m.plan} pos={m.telem?.pos || 0} colorHex={cat.colorHex} onSeek={m.seek} />
              ) : (
                <div className="bg-panel border border-line rounded-xl p-8 text-center text-mute text-sm">
                  Load a song to see its timeline
                </div>
              )}
            </div>

            <CommandRate cmds={cmds} />
            <div className="mt-3 pt-2.5 text-xs min-h-4 border-t border-line"
                 style={{ color: status.ok ? "#5aa9ff" : "#e0667a" }}>{status.msg}</div>
          </div>
        </div>

        {/* CONTROLS */}
        <div className={cx(page === "controls" ? "" : "hidden")}>
          <ControlsPage act={act} groups={cat.groups} families={cat.families}
                        micOn={m.micOn} onMicChange={m.setMicOn} />
        </div>

        {/* HOW IT WORKS */}
        <div className={cx(page === "how" ? "" : "hidden")}>
          <HowItWorks ex={ex} />
        </div>
      </main>
    </>
  );
}
