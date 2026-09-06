export const API_BASE = "";

export type Segment = {
  segment: string;
  beats: number;
  duration_s: number;
  start_s: number | null;
  end_s: number | null;
  window_s: number | null;
  color: string;
};

export type BeatSummary = {
  beat: string;
  beat_id: string;
  run_id: string;
  segment: string | null;
  start_s: number | null;
  end_s: number | null;
  verdict: string;
  ctx_state_ok: boolean;
  shot_count: number;
  duration_s: number;
  media: string[];
};

export type IndexDoc = {
  generated_at: string;
  beat_count: number;
  shot_count: number;
  total_duration_s: number;
  media_count: number;
  verdicts: Record<string, number>;
  ctx_state_errors: string[];
  segments: Segment[];
  beats: BeatSummary[];
  // presentation intro (P10G-BEAT-000), reported separately from the 44 canon beats
  intro?: BeatSummary | null;
  intro_duration_s?: number;
  canon_beat_count?: number;
  canon_shot_count?: number;
  canon_duration_s?: number;
  canon_bound_duration_s?: number;
  canon_unbound_duration_s?: number;
  showcase_duration_s?: number;
};

export const INTRO_BEAT_ID = "P10G-BEAT-000";

export const isIntro = (b: { beat_id: string }) => b.beat_id === INTRO_BEAT_ID;

/** Canon beat count with a fallback for snapshots built before the intro split. */
export const canonCount = (idx: IndexDoc) =>
  idx.canon_beat_count ??
  idx.beats.filter((b) => !isIntro(b)).length;

export const canonRuntime = (idx: IndexDoc) =>
  idx.canon_duration_s ??
  idx.beats.filter((b) => !isIntro(b)).reduce((n, b) => n + b.duration_s, 0);

export type Shot = {
  scene_no: number;
  shot_no: number;
  duration_s: number;
  hero_render?: boolean;
  intent?: string;
  subject?: string;
  location?: string;
  time_of_day?: string;
  characters_present?: string[];
  blocking?: string;
  performance?: string;
  atmosphere?: string;
  continuity_notes?: string;
  camera?: Record<string, unknown>;
  light?: Record<string, unknown>;
  look?: Record<string, unknown>;
  audio?: Record<string, unknown>;
};

export type BeatDoc = BeatSummary & {
  shots: Shot[];
  prompts: Record<string, unknown>;
  references: Record<string, unknown>;
  validate: Record<string, unknown>;
  continuity_delta: string | null;
  media_urls: string[];
};

export type Tier = {
  image: string;
  video: string;
  image_res: string;
  video_res: string;
  usd_image: number;
  usd_video_per_s: number;
};

export type Health = {
  status: string;
  source: string;
  generated_at: string;
  beat_count: number;
  verdicts: Record<string, number>;
  media_count: number;
  env: Record<string, unknown>;
};

export async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const fmtDur = (s: number) =>
  `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;

export const SEGMENT_LABEL: Record<string, string> = {
  intro: "Intro",
  prologue: "Prologue",
  act_1: "Act I",
  act_2a: "Act II-A",
  act_2b: "Act II-B",
  act_3: "Act III",
  epilogue: "Epilogue",
  unbound: "Unbound",
};
