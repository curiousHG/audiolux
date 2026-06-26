import { useState } from "react";
import { card } from "@/ui";
import { useStrip } from "@/hooks/useStrip";
import { useCatalog } from "@/hooks/useCatalog";
import { useMusic } from "@/hooks/useMusic";
import Header from "@/components/Header";
import Drawer from "@/components/Drawer";
import Player from "@/components/Player";
import Telemetry from "@/components/Telemetry";
import CommandRate from "@/components/CommandRate";
import PowerColor from "@/components/PowerColor";
import Effects from "@/components/Effects";
import MusicEngine from "@/components/MusicEngine";
import Soundboard from "@/components/Soundboard";

export default function App() {
  const { act, status, connected, cmds } = useStrip();
  const cat = useCatalog();
  const m = useMusic(act);
  const [drawer, setDrawer] = useState(false);
  const [powerOn, setPowerOn] = useState(true);

  const onPower = (on: boolean) => { setPowerOn(on); act("/api/power?on=" + (on ? 1 : 0)); };

  return (
    <>
      <Header connected={connected} powerOn={powerOn} onPower={onPower} onMenu={() => setDrawer((o) => !o)} />

      <main className="max-w-[1180px] mx-auto px-4 sm:px-6 py-5">
        <div className={card}>
          {/* one view: the music being played + all of its telemetry, side by side */}
          <div className="grid lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] gap-6 items-start">
            <Player ref={m.playerRef} active={!m.micOn} smart={m.smart} onSmart={m.onSmart}
                    strobe={m.strobe} onStrobe={m.onStrobe}
                    onTrackState={m.onTrackState} onPlayingChange={m.onPlaying} />
            <Telemetry telem={m.telem} hist={m.hist.current} colorHex={cat.colorHex}
                       barColors={cat.barColors} num2name={cat.num2name} />
          </div>
          <CommandRate cmds={cmds} />
          <div className="mt-[18px] pt-2.5 text-xs min-h-4 border-t border-line"
               style={{ color: status.ok ? "#5aa9ff" : "#e0667a" }}>{status.msg}</div>
        </div>
      </main>

      <Drawer open={drawer} onClose={() => setDrawer(false)}>
        <PowerColor act={act} />
        <Effects act={act} groups={cat.groups} />
        <MusicEngine act={act} families={cat.families} micOn={m.micOn} onMicChange={m.setMicOn} />
        <Soundboard act={act} />
      </Drawer>
    </>
  );
}
