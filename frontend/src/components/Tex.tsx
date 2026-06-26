import katex from "katex";
import "katex/dist/katex.min.css";

// Render a LaTeX string with KaTeX.
export default function Tex({ tex, block }: { tex: string; block?: boolean }) {
  const html = katex.renderToString(tex, { throwOnError: false, displayMode: !!block });
  return (
    <span className={block ? "block my-1.5 overflow-x-auto text-[#e7e9ee]" : "inline-block align-middle"}
          dangerouslySetInnerHTML={{ __html: html }} />
  );
}
