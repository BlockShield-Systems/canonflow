"use client";
import { SEGMENT_LABEL, type BeatSummary } from "@/lib/api";

export default function BeatList({
  beats,
  colors,
  active,
  onSelect,
}: {
  beats: BeatSummary[];
  colors: Record<string, string>;
  active: string | null;
  onSelect: (beat: string) => void;
}) {
  return (
    <div className="min-w-0">
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-edge bg-panel/95 px-3 py-2 backdrop-blur">
        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-mut">Beats</span>
        <span className="text-[10px] tabular-nums text-mut">{beats.length}</span>
      </div>
      <ul className="p-1.5">
        {beats.map((b) => {
          const seg = b.segment ?? "unbound";
          const on = active === b.beat;
          return (
            <li key={b.beat}>
              <button
                type="button"
                onClick={() => onSelect(b.beat)}
                className={`mb-0.5 flex w-full min-w-0 items-center gap-2 rounded-md border-l-2 px-2 py-1.5 text-left transition-colors ${
                  on ? "bg-panel2 text-fg" : "text-mut hover:bg-panel2/60 hover:text-fg"
                }`}
                style={{ borderLeftColor: colors[seg] ?? "#3a4553" }}
              >
                <span className="w-8 shrink-0 font-mono text-[11.5px] tabular-nums">{b.beat}</span>
                <span className="min-w-0 flex-1 truncate text-[11.5px]">{SEGMENT_LABEL[seg] ?? seg}</span>
                <span className="shrink-0 text-[10.5px] tabular-nums opacity-70">{b.duration_s}s</span>
                <span
                  title={`${b.verdict} / ctx_state ${b.ctx_state_ok ? "ok" : "fail"}`}
                  className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                    b.verdict === "PASS" && b.ctx_state_ok ? "bg-emerald-400" : "bg-rose-400"
                  }`}
                />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
