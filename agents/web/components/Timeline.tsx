"use client";
import { SEGMENT_LABEL, type Segment } from "@/lib/api";

export default function Timeline({
  segments,
  active,
  onSelect,
}: {
  segments: Segment[];
  active: string | null;
  onSelect: (segment: string | null) => void;
}) {
  const total = segments.reduce((acc, s) => acc + s.duration_s, 0) || 1;
  return (
    <div className="min-w-0">
      <div className="flex h-8 w-full overflow-hidden rounded-md border border-edge">
        {segments.map((s) => (
          <button
            key={s.segment}
            type="button"
            onClick={() => onSelect(active === s.segment ? null : s.segment)}
            title={`${SEGMENT_LABEL[s.segment] ?? s.segment} - ${s.beats} beats / ${s.duration_s}s`}
            style={{
              width: `${(s.duration_s / total) * 100}%`,
              backgroundColor: s.color,
              opacity: active === null || active === s.segment ? 1 : 0.25,
            }}
            className="group relative h-full border-r border-ink/60 transition-opacity last:border-r-0"
          >
            <span className="pointer-events-none absolute inset-0 flex items-center justify-center text-[10px] font-bold text-ink/80 opacity-0 group-hover:opacity-100">
              {s.beats}
            </span>
          </button>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
        {segments.map((s) => (
          <button
            key={s.segment}
            type="button"
            onClick={() => onSelect(active === s.segment ? null : s.segment)}
            className={`flex items-center gap-1.5 rounded px-1 py-0.5 ${
              active === s.segment ? "bg-panel2 text-fg" : "text-mut hover:text-fg"
            }`}
          >
            <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: s.color }} />
            {SEGMENT_LABEL[s.segment] ?? s.segment}
            <span className="tabular-nums opacity-70">{s.duration_s}s</span>
          </button>
        ))}
        {active ? (
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="ml-1 rounded border border-edge px-1.5 py-0.5 text-mut hover:text-fg"
          >
            Filter aus
          </button>
        ) : null}
      </div>
    </div>
  );
}
