import { cx } from "@/ui";

// Draggable splitter. axis "x" = vertical bar dragged horizontally; "y" = horizontal
// bar dragged vertically. Calls onResize with the pointer delta (px) as it moves.
export default function Divider({ axis, onResize }: { axis: "x" | "y"; onResize: (delta: number) => void }) {
  const onDown = (e: React.PointerEvent) => {
    e.preventDefault();
    let last = axis === "x" ? e.clientX : e.clientY;
    const move = (ev: PointerEvent) => {
      const cur = axis === "x" ? ev.clientX : ev.clientY;
      onResize(cur - last); last = cur;
    };
    const up = () => {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", up);
      document.body.style.userSelect = "";
    };
    document.body.style.userSelect = "none";
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", up);
  };
  return (
    <div onPointerDown={onDown}
         className={cx("shrink-0 rounded transition-colors bg-line hover:bg-accent/60 group",
           axis === "x" ? "w-1.5 cursor-col-resize self-stretch" : "h-1.5 cursor-row-resize")}>
      <div className={cx("mx-auto my-auto bg-dim/60 rounded-full",
        axis === "x" ? "w-0.5 h-6 mt-[40%]" : "h-0.5 w-8")} />
    </div>
  );
}
