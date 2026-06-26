import { Menu, Power } from "lucide-react";
import { cx } from "@/ui";

interface Props {
  connected: boolean;
  powerOn: boolean;
  onPower: (on: boolean) => void;
  onMenu: () => void;
}

export default function Header({ connected, powerOn, onPower, onMenu }: Props) {
  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 bg-card/95 backdrop-blur border-b border-line px-4 sm:px-6 py-3">
      <button onClick={onMenu} aria-label="Controls"
              className="p-2 rounded-lg bg-btn hover:bg-btn2 text-ink cursor-pointer transition-colors">
        <Menu size={18} />
      </button>
      <h1 className="text-lg font-semibold tracking-[.3px]">audiolux</h1>
      <span className={cx("text-[11px] px-2.5 py-0.5 rounded-full",
        connected ? "bg-[#163a2a] text-[#57d090]" : "bg-[#3a1820] text-[#e0667a]")}>
        {connected ? "connected" : "not connected"}
      </span>
      <div className="flex-1" />
      <button onClick={() => onPower(!powerOn)}
              className={cx("flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm text-white cursor-pointer transition-colors",
                powerOn ? "bg-on hover:brightness-110" : "bg-off hover:brightness-110")}>
        <Power size={16} /> {powerOn ? "On" : "Off"}
      </button>
    </header>
  );
}
