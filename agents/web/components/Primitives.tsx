"use client";
import type { ReactNode } from "react";

const TONES: Record<string, string> = {
  neutral: "border-edge bg-panel2 text-mut",
  ok: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  warn: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  bad: "border-rose-500/40 bg-rose-500/10 text-rose-300",
  info: "border-sky-500/40 bg-sky-500/10 text-sky-300",
};

export function Pill({
  children,
  tone = "neutral",
  title,
}: {
  children: ReactNode;
  tone?: "neutral" | "ok" | "warn" | "bad" | "info";
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[10.5px] font-medium uppercase tracking-[0.08em] ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

export function Metric({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-[0.14em] text-mut">{label}</div>
      <div className="truncate text-xl font-semibold tabular-nums">{value}</div>
      {sub ? <div className="truncate text-[11px] text-mut">{sub}</div> : null}
    </div>
  );
}

export function Panel({
  title,
  right,
  children,
  className = "",
}: {
  title: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`min-w-0 rounded-xl border border-edge bg-panel ${className}`}>
      <header className="flex items-center justify-between gap-3 border-b border-edge px-3 py-2">
        <h3 className="truncate text-[11px] font-semibold uppercase tracking-[0.14em] text-mut">{title}</h3>
        {right}
      </header>
      <div className="min-w-0 p-3">{children}</div>
    </section>
  );
}

export function Field({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null || value === "") return null;
  if (Array.isArray(value) && value.length === 0) return null;
  const text = Array.isArray(value)
    ? value.map((v) => (typeof v === "object" ? JSON.stringify(v) : String(v))).join(", ")
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-[0.14em] text-mut">{label.replace(/_/g, " ")}</div>
      <div className="break-words text-[12.5px] leading-relaxed">{text}</div>
    </div>
  );
}

export function Json({ data, maxH = "60vh" }: { data: unknown; maxH?: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-edge bg-ink">
      <pre
        style={{ maxHeight: maxH }}
        className="min-w-0 overflow-auto whitespace-pre p-3 font-mono text-[11px] leading-5"
      >
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
