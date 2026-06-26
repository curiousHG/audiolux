import type { ReactNode } from "react";
import { X } from "lucide-react";
import { cx } from "@/ui";

interface Props {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

// Slide-in left drawer holding the manual controls + soundboard.
export default function Drawer({ open, onClose, children }: Props) {
  return (
    <>
      <div onClick={onClose}
           className={cx("fixed inset-0 bg-black/50 z-40 transition-opacity duration-200",
             open ? "opacity-100" : "opacity-0 pointer-events-none")} />
      <aside className={cx("fixed top-0 left-0 h-full w-[380px] max-w-[88vw] bg-card border-r border-line z-50 overflow-y-auto p-5 transition-transform duration-200",
        open ? "translate-x-0" : "-translate-x-full")}>
        <div className="flex items-center justify-between mb-4">
          <span className="text-[11px] uppercase tracking-[1.2px] text-accent font-semibold">Controls</span>
          <button onClick={onClose} aria-label="Close"
                  className="p-1.5 rounded-lg bg-btn hover:bg-btn2 text-ink cursor-pointer transition-colors">
            <X size={16} />
          </button>
        </div>
        <div className="flex flex-col gap-7">{children}</div>
      </aside>
    </>
  );
}
