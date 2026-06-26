import type { FamilyInfo, ModeGroup } from "@/api";
import { card } from "@/ui";
import PowerColor from "@/components/PowerColor";
import Effects from "@/components/Effects";
import MusicEngine from "@/components/MusicEngine";
import Soundboard from "@/components/Soundboard";

interface Props {
  act: (u: string) => void;
  groups: ModeGroup[];
  families: FamilyInfo[];
  micOn: boolean;
  onMicChange: (on: boolean) => void;
}

// Manual controls page: colour, effects, mic engine, soundboard.
export default function ControlsPage({ act, groups, families, micOn, onMicChange }: Props) {
  return (
    <div className={card + " flex flex-col gap-6"}>
      <div className="grid lg:grid-cols-3 gap-6 items-start">
        <PowerColor act={act} />
        <Effects act={act} groups={groups} />
        <MusicEngine act={act} families={families} micOn={micOn} onMicChange={onMicChange} />
      </div>
      <Soundboard act={act} />
    </div>
  );
}
