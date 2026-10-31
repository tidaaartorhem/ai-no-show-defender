import type { Segment } from "../types";

const SEGMENT_CLASS: Record<Segment, string> = {
  CRITICAL: "bad",
  ELEVATED: "warn",
  LOW: "ok",
};

export function SegmentBadge({ segment }: { segment: Segment }) {
  return (
    <span className={`pill ${SEGMENT_CLASS[segment] ?? "neutral"}`}>
      {segment}
    </span>
  );
}

export function ScoreBar({ score, segment }: { score: number; segment: Segment }) {
  const cls = segment === "CRITICAL" ? "bad" : segment === "ELEVATED" ? "warn" : "ok";
  return (
    <span className="confbar">
      <span className="confbar-track">
        <span className={`confbar-fill ${cls}`} style={{ width: `${Math.min(100, score)}%` }} />
      </span>
      <span className="confbar-num mono">{score}/100</span>
    </span>
  );
}
