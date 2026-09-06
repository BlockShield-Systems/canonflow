"use client";
import { useEffect, useState } from "react";
import ShotCard from "@/components/ShotCard";
import { Json, Panel, Pill } from "@/components/Primitives";
import { SEGMENT_LABEL, type BeatDoc, type Tier } from "@/lib/api";

type Tab = "shots" | "prompts" | "validate" | "references" | "cost" | "raw";
const TABS: { id: Tab; label: string }[] = [
  { id: "shots", label: "Shots" },
  { id: "prompts", label: "Prompts" },
  { id: "validate", label: "Validator" },
  { id: "references", label: "References" },
  { id: "cost", label: "Cost" },
  { id: "raw", label: "Raw" },
];

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => setDone(false), 1200);
    return () => clearTimeout(t);
  }, [done]);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
        } catch {
          setDone(false);
        }
      }}
      className="shrink-0 rounded border border-edge px-2 py-0.5 text-[10px] uppercase tracking-wide text-mut hover:text-fg"
    >
      {done ? "copied" : "copy"}
    </button>
  );
}

export default function BeatDetail({
  beat,
  loading,
  error,
  tiers,
}: {
  beat: BeatDoc | null;
  loading: boolean;
  error: string | null;
  tiers: Record<string, Tier>;
}) {
  const [tab, setTab] = useState<Tab>("shots");

  if (error) {
    return <div className="p-4 text-[12.5px] text-rose-300">API-Fehler: {error}</div>;
  }
  if (!beat) {
    return (
      <div className="p-4 text-[12.5px] text-mut">
        {loading ? "lade Beat ..." : "Beat links auswaehlen (Pfeiltasten / j,k navigieren)"}
      </div>
    );
  }

  const seg = beat.segment ?? "unbound";
  const promptEntries = Object.entries(beat.prompts ?? {});

  return (
    <div className="min-w-0">
      <div className="sticky top-0 z-20 border-b border-edge bg-panel/95 backdrop-blur">
        <div className="flex flex-wrap items-center gap-2 px-4 pt-3">
          <h2 className="font-mono text-[13px] font-semibold">{beat.beat_id}</h2>
          <Pill tone={beat.verdict === "PASS" ? "ok" : "bad"}>canon {beat.verdict}</Pill>
          <Pill tone={beat.ctx_state_ok ? "ok" : "bad"}>ctx_state {beat.ctx_state_ok ? "ok" : "fail"}</Pill>
          <Pill>{SEGMENT_LABEL[seg] ?? seg}</Pill>
          {beat.start_s !== null && beat.end_s !== null ? (
            <Pill tone="info">
              {beat.start_s}s - {beat.end_s}s
            </Pill>
          ) : (
            <Pill tone="warn">no window</Pill>
          )}
          <Pill>{beat.shot_count} shots</Pill>
          <Pill>{beat.duration_s}s</Pill>
          <span className="min-w-0 flex-1 truncate text-right font-mono text-[10.5px] text-mut">{beat.run_id}</span>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pt-2">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`shrink-0 rounded-t-md border-b-2 px-3 py-1.5 text-[11.5px] font-medium uppercase tracking-[0.08em] transition-colors ${
                tab === t.id
                  ? "border-sky-400 bg-panel2 text-fg"
                  : "border-transparent text-mut hover:bg-panel2/50 hover:text-fg"
              }`}
            >
              {t.label}
              {t.id === "prompts" && promptEntries.length ? (
                <span className="ml-1.5 tabular-nums opacity-60">{promptEntries.length}</span>
              ) : null}
            </button>
          ))}
        </nav>
      </div>

      <div className="min-w-0 space-y-3 p-4">
        {beat.media_urls?.length ? (
          <Panel title={`media (${beat.media_urls.length})`}>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {beat.media_urls.map((u) => (
                <a key={u} href={u} target="_blank" rel="noreferrer" className="min-w-0">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={u} alt={u} className="h-28 w-full rounded-md border border-edge object-cover" />
                </a>
              ))}
            </div>
          </Panel>
        ) : null}

        {tab === "shots" ? (
          <div className="space-y-3">
            {beat.shots.map((s, i) => (
              <ShotCard key={`${s.scene_no}-${s.shot_no}-${i}`} shot={s} />
            ))}
          </div>
        ) : null}

        {tab === "prompts" ? (
          promptEntries.length === 0 ? (
            <div className="text-[12.5px] text-mut">keine Prompts in diesem Beat</div>
          ) : (
            <div className="space-y-3">
              {promptEntries.map(([key, val]) => {
                const text = typeof val === "string" ? val : JSON.stringify(val, null, 2);
                return (
                  <Panel key={key} title={key} right={<CopyButton text={text} />}>
                    {typeof val === "string" ? (
                      <p className="max-h-[45vh] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-edge bg-ink p-3 font-mono text-[11.5px] leading-5">
                        {val}
                      </p>
                    ) : (
                      <Json data={val} maxH="45vh" />
                    )}
                  </Panel>
                );
              })}
            </div>
          )
        ) : null}

        {tab === "validate" ? (
          <div className="space-y-3">
            <Panel title="continuity delta">
              <p className="break-words text-[12.5px] leading-relaxed">{beat.continuity_delta ?? "-"}</p>
            </Panel>
            <Panel title="validator payload">
              <Json data={beat.validate} maxH="55vh" />
            </Panel>
          </div>
        ) : null}

        {tab === "references" ? (
          <Panel title="references">
            <Json data={beat.references} maxH="65vh" />
          </Panel>
        ) : null}

        {tab === "cost" ? (
          <Panel title={`render cost estimate - ${beat.shot_count} keyframes / ${beat.duration_s}s video`}>
            <div className="min-w-0 overflow-x-auto">
              <table className="w-full min-w-[620px] text-[12px]">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-[0.12em] text-mut">
                    <th className="py-1.5 pr-3">tier</th>
                    <th className="py-1.5 pr-3">image model</th>
                    <th className="py-1.5 pr-3">video model</th>
                    <th className="py-1.5 pr-3 text-right">images</th>
                    <th className="py-1.5 pr-3 text-right">video</th>
                    <th className="py-1.5 text-right">total</th>
                  </tr>
                </thead>
                <tbody className="font-mono tabular-nums">
                  {Object.entries(tiers).map(([name, t]) => {
                    const img = beat.shot_count * t.usd_image;
                    const vid = beat.duration_s * t.usd_video_per_s;
                    return (
                      <tr key={name} className="border-t border-edge">
                        <td className="py-1.5 pr-3 font-sans">{name}</td>
                        <td className="py-1.5 pr-3 text-mut">
                          {t.image} <span className="opacity-60">{t.image_res}</span>
                        </td>
                        <td className="py-1.5 pr-3 text-mut">
                          {t.video} <span className="opacity-60">{t.video_res}</span>
                        </td>
                        <td className="py-1.5 pr-3 text-right">${img.toFixed(2)}</td>
                        <td className="py-1.5 pr-3 text-right">${vid.toFixed(2)}</td>
                        <td className="py-1.5 text-right font-semibold">${(img + vid).toFixed(2)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px] text-mut">
              Annahme: 1 Keyframe pro Shot, Videolaenge = Beat-Dauer. Render laeuft nur nach explizitem
              Human-Gate.
            </p>
          </Panel>
        ) : null}

        {tab === "raw" ? (
          <Panel title="beat document">
            <Json data={beat} maxH="70vh" />
          </Panel>
        ) : null}
      </div>
    </div>
  );
}
