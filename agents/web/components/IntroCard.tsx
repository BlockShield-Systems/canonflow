"use client";

import type { BeatSummary } from "@/lib/api";

type Props = {
  intro: BeatSummary | null | undefined;
  selected: boolean;
  onSelect: (beatId: string) => void;
};

/**
 * The presentation intro (P10G-BEAT-000) is a 30 s title prelude, not one of the
 * 44 canonical narrative beats. It sits beside the segment bar rather than inside
 * it, so the canon story clock and the PASS ratio stay untouched.
 */
export function IntroCard({ intro, selected, onSelect }: Props) {
  if (!intro) return null;
  const ok = intro.verdict === "PASS";
  return (
    <button
      type="button"
      onClick={() => onSelect(intro.beat_id)}
      title={`${intro.beat_id} - presentation intro - ${intro.shot_count} shots - ${intro.duration_s}s - outside canon`}
      className={[
        "group flex h-[34px] items-center gap-2 rounded border px-2",
        "text-left transition-colors",
        selected
          ? "border-neutral-400 bg-neutral-800"
          : "border-edge bg-neutral-900/60 hover:border-neutral-500 hover:bg-neutral-800",
      ].join(" ")}
    >
      <span
        aria-hidden
        className="h-[18px] w-[3px] shrink-0 rounded-sm"
        style={{ background: "#9aa0a6" }}
      />
      <span className="min-w-0 leading-tight">
        <span className="block truncate text-[11px] font-semibold uppercase tracking-wide text-fg">
          Intro
        </span>
        <span className="block truncate text-[10px] text-mut">
          {intro.shot_count} shots &middot; {intro.duration_s}s &middot; pre-canon
        </span>
      </span>
      <span
        aria-hidden
        className={[
          "ml-1 h-1.5 w-1.5 shrink-0 rounded-full",
          ok ? "bg-emerald-400" : "bg-rose-400",
        ].join(" ")}
      />
    </button>
  );
}
