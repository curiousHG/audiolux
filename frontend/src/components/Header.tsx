import { Power, Music, SlidersHorizontal, BookOpen } from "lucide-react";
import { cx } from "@/ui";

export type Page = "player" | "controls" | "how";

const TABS: [Page, string, typeof Music][] = [
  ["player", "Player", Music],
  ["controls", "Controls", SlidersHorizontal],
  ["how", "How it works", BookOpen],
];

interface Props {
  page: Page;
  setPage: (p: Page) => void;
  connected: boolean;
  powerOn: boolean;
  onPower: (on: boolean) => void;
}

export default function Header({ page, setPage, connected, powerOn, onPower }: Props) {
  return (
    <header className="shrink-0 flex items-center gap-3 flex-wrap bg-card border-b border-line px-4 sm:px-6 py-2">
      <h1 className="text-lg font-semibold tracking-[.3px]">audiolux</h1>
      <nav className="flex gap-1 ml-1">
        {TABS.map(([id, label, Icon]) => (
          <button key={id} onClick={() => setPage(id)}
                  className={cx("flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm cursor-pointer transition-colors",
                    page === id ? "bg-btn2 text-ink" : "text-mute hover:text-ink hover:bg-btn")}>
            <Icon size={15} /> <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </nav>
      <div className="flex-1" />
      <span className={cx("text-[11px] px-2.5 py-0.5 rounded-full",
        connected ? "bg-[#163a2a] text-[#57d090]" : "bg-[#3a1820] text-[#e0667a]")}>
        {connected ? "connected" : "not connected"}
      </span>
      <button onClick={() => onPower(!powerOn)}
              className={cx("flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm text-white cursor-pointer transition-colors hover:brightness-110",
                powerOn ? "bg-on" : "bg-off")}>
        <Power size={16} /> {powerOn ? "On" : "Off"}
      </button>
    </header>
  );
}
