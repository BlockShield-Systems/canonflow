"use client";
import { Field, Pill } from "@/components/Primitives";
import type { Shot } from "@/lib/api";

function DictGroup({ title, data }: { title: string; data?: Record<string, unknown> }) {
  if (!data || Object.keys(data).length === 0) return null;
  return (
    <div className="min-w-0 rounded-lg border border-edge bg-panel2 p-2.5">
      <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-mut">{title}</div>
      <dl className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        {Object.entries(data).map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="text-[10px] uppercase tracking-wide text-mut">{k.replace(/_/g, " ")}</dt>
            <dd className="break-words text-[12px]">
              {v === null || v === undefined
                ? "-"
                : typeof v === "object"
                  ? JSON.stringify(v)
                  : String(v)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function ShotCard({ shot }: { shot: Shot }) {
  return (
    <article className="min-w-0 rounded-xl border border-edge bg-panel">
      <header className="flex flex-wrap items-center gap-2 border-b border-edge px-3 py-2">
        <span className="font-mono text-[12px] tabular-nums">
          S{String(shot.scene_no).padStart(2, "0")} / SH{String(shot.shot_no).padStart(2, "0")}
        </span>
        <Pill tone="info">{shot.duration_s}s</Pill>
        {shot.hero_render ? <Pill tone="warn">hero render</Pill> : null}
        <span className="min-w-0 flex-1 truncate text-right text-[11.5px] text-mut">{shot.intent ?? ""}</span>
      </header>
      <div className="min-w-0 space-y-3 p-3">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <Field label="subject" value={shot.subject} />
          <Field label="location" value={shot.location} />
          <Field label="time_of_day" value={shot.time_of_day} />
          <Field label="characters_present" value={shot.characters_present} />
          <Field label="blocking" value={shot.blocking} />
          <Field label="performance" value={shot.performance} />
          <Field label="atmosphere" value={shot.atmosphere} />
          <Field label="continuity_notes" value={shot.continuity_notes} />
        </div>
        <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-2">
          <DictGroup title="camera" data={shot.camera} />
          <DictGroup title="light" data={shot.light} />
          <DictGroup title="look" data={shot.look} />
          <DictGroup title="audio" data={shot.audio} />
        </div>
      </div>
    </article>
  );
}
