"use client";
import { useEffect, useMemo, useState } from "react";
import BeatDetail from "@/components/BeatDetail";
import BeatList from "@/components/BeatList";
import Timeline from "@/components/Timeline";
import { IntroCard } from "@/components/IntroCard";
import { Metric, Pill } from "@/components/Primitives";
import {
  canonCount,
  canonRuntime,
  fmtDur,
  getJSON,
  isIntro,
  type BeatDoc,
  type Health,
  type IndexDoc,
  type Tier,
} from "@/lib/api";

export default function Page() {
  const [idx, setIdx] = useState<IndexDoc | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [tiers, setTiers] = useState<Record<string, Tier>>({});
  const [segment, setSegment] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [beat, setBeat] = useState<BeatDoc | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showStats, setShowStats] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [i, h, t] = await Promise.all([
          getJSON<IndexDoc>("/api/timeline"),
          getJSON<Health>("/api/health"),
          getJSON<Record<string, Tier>>("/api/tiers"),
        ]);
        if (!alive) return;
        setIdx(i);
        setHealth(h);
        setTiers(t);
        const hash = window.location.hash.replace("#", "");
        const first = i.beats.find((b) => b.beat === hash) ?? i.beats[0];
        if (first) setSel(first.beat);
      } catch (e) {
        if (alive) setError(String(e));
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!sel) return;
    let alive = true;
    setLoading(true);
    (async () => {
      try {
        const d = await getJSON<BeatDoc>(`/api/beats/${sel}`);
        if (!alive) return;
        setBeat(d);
        setError(null);
        window.history.replaceState(null, "", `#${sel}`);
      } catch (e) {
        if (alive) setError(String(e));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [sel]);

  const colors = useMemo(() => {
    const m: Record<string, string> = {};
    for (const s of idx?.segments ?? []) m[s.segment] = s.color;
    return m;
  }, [idx]);

  const canonBeats = useMemo(
    () => (idx?.beats ?? []).filter((b) => !isIntro(b)),
    [idx],
  );

  const visible = useMemo(
    () => canonBeats.filter((b) => segment === null || (b.segment ?? "unbound") === segment),
    [canonBeats, segment],
  );

  // PASS ratio is canon-only: the presentation intro is not one of the 44 beats.
  const canonTotal = idx ? canonCount(idx) : 0;
  const canonPass = useMemo(
    () => canonBeats.filter((b) => b.verdict === "PASS").length,
    [canonBeats],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tgt = e.target;
      if (tgt instanceof HTMLInputElement || tgt instanceof HTMLTextAreaElement) return;
      const down = e.key === "ArrowDown" || e.key === "j";
      const up = e.key === "ArrowUp" || e.key === "k";
      if (!down && !up) return;
      if (visible.length === 0) return;
      e.preventDefault();
      const i = visible.findIndex((b) => b.beat === sel);
      const next = i < 0 ? 0 : Math.min(visible.length - 1, Math.max(0, i + (down ? 1 : -1)));
      setSel(visible[next].beat);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [visible, sel]);


  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <header className="min-w-0 shrink-0 border-b border-edge bg-panel/60 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-[15px] font-bold tracking-[0.18em]">CANONFLOW</h1>
          <span className="text-[11px] text-mut">
            agentic beat-to-prompt pipeline &middot; canon validation &middot; ClickHouse continuity state
          </span>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {idx ? (
              <Pill tone={canonPass === canonTotal ? "ok" : "bad"}>
                {canonPass}/{canonTotal} canon PASS
              </Pill>
            ) : null}
            {idx ? (
              <Pill tone={idx.ctx_state_errors.length === 0 ? "ok" : "bad"}>
                ctx_state {idx.ctx_state_errors.length === 0 ? "clean" : `${idx.ctx_state_errors.length} err`}
              </Pill>
            ) : null}
            {health ? <Pill tone="info">{health.source}</Pill> : null}
            {idx ? <span className="font-mono text-[10px] text-mut">{idx.generated_at}</span> : null}
            <button
              type="button"
              onClick={() => setShowStats((v) => !v)}
              className="rounded border border-edge px-2 py-0.5 text-[10px] uppercase tracking-wide text-mut hover:text-fg"
            >
              {showStats ? "compact" : "stats"}
            </button>
            <a
              href="/review/"
              className="rounded border border-edge px-2 py-0.5 text-[10px] uppercase tracking-wide text-mut hover:text-fg"
            >
              ops console
            </a>
          </div>
        </div>

        {showStats && idx ? (
          <div className="mt-3 grid grid-cols-2 gap-4 md:grid-cols-5">
            <Metric
              label="beats"
              value={canonTotal}
              sub={idx.intro ? "canon + 1 intro" : "agent-generated"}
            />
            <Metric label="shots" value={idx.shot_count} sub={`${visible.length} in view`} />
            <Metric
              label="runtime"
              value={fmtDur(canonRuntime(idx))}
              sub={
                idx.canon_bound_duration_s
                  ? `${idx.canon_bound_duration_s} s bound + ${idx.canon_unbound_duration_s ?? 0} s unbound`
                  : `${canonRuntime(idx)} s`
              }
            />
            <Metric label="canon" value={`${canonPass}/${canonTotal}`} sub="validator PASS" />
            <Metric label="renders" value={idx.media_count} sub="media artifacts" />
          </div>
        ) : null}

        {idx ? (
          <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-start">
            <IntroCard
              intro={idx.intro}
              selected={sel === idx.intro?.beat_id}
              onSelect={(id) => {
                setSegment(null);
                setSel(id);
              }}
            />
            <div className="min-w-0 flex-1">
              <Timeline segments={idx.segments} active={segment} onSelect={setSegment} />
            </div>
          </div>
        ) : null}
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[clamp(200px,17vw,280px)_minmax(0,1fr)]">
        <aside className="min-h-0 min-w-0 overflow-y-auto border-r border-edge bg-panel/40">
          <BeatList beats={visible} colors={colors} active={sel} onSelect={setSel} />
        </aside>
        <main className="min-h-0 min-w-0 overflow-y-auto">
          <BeatDetail beat={beat} loading={loading} error={error} tiers={tiers} />
        </main>
      </div>
    </div>
  );
}
