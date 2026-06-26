// Shared inline-Tailwind class strings (composed in JSX with template literals).
export const card = "w-full bg-card border border-line rounded-2xl p-3 sm:p-4";
export const h2 = "text-[11px] font-semibold uppercase tracking-[1.2px] text-accent border-b border-line pb-[7px] mb-[10px]";
export const sectionTop = "mt-[22px] pt-[14px] border-t border-line";
export const row = "flex gap-2.5 my-3";
export const btn =
  "flex-1 py-[11px] rounded-xl bg-btn hover:bg-btn2 text-ink text-sm cursor-pointer transition-colors disabled:opacity-40 disabled:cursor-default";
export const btnSmall = "shrink-0 px-3 py-2 rounded-xl bg-btn2 text-[13px] text-ink cursor-pointer transition-colors hover:bg-btn";
export const btnMini = "shrink-0 px-2.5 py-1 rounded-lg bg-btn2 text-[11px] text-ink cursor-pointer transition-colors hover:bg-btn";
export const label = "block text-xs text-mute mt-3.5 mb-1.5";
export const val = "float-right text-accent";
export const note = "text-[11px] text-dim font-normal";
export const card2 = "bg-panel border border-line rounded-xl p-3";
export const ro = "flex-1 min-w-[90px] bg-panel border border-line rounded-[10px] px-2.5 py-2 text-center";

export const on = (active: boolean) => (active ? " !bg-on" : "");
export const cx = (...parts: (string | false | undefined)[]) => parts.filter(Boolean).join(" ");
