import { useState } from "react";
import { fmtPct, fmtUSD, rescueQueue, summary } from "../data";
import type { RescueEntry, Segment } from "../types";
import { ScoreBar, SegmentBadge } from "./shared";

type ActionState = "pending" | "approved" | "dismissed";

const SEGMENT_ORDER: Record<Segment, number> = {
  CRITICAL: 0,
  ELEVATED: 1,
  LOW: 2,
};

function RescueCard({
  entry,
  state,
  onAction,
}: {
  entry: RescueEntry;
  state: ActionState;
  onAction: (s: ActionState) => void;
}) {
  return (
    <div className="card lead-card">
      <div className="lead-head">
        <div>
          <b>{entry.patient}</b>
          <span className="muted small">
            {" "}· {entry.visit_type} · {entry.appointment_day} {entry.appointment_time} ·
            fee <b className="mono">{fmtUSD(entry.fee)}</b>
          </span>
        </div>
        <SegmentBadge segment={entry.segment} />
      </div>
      <div className="bar-row">
        <span className="bar-label">No-show risk</span>
        <ScoreBar score={entry.score} segment={entry.segment} />
        <span className="bar-value">
          predicted probability <b className="mono">{(entry.prob * 100).toFixed(1)}%</b>
        </span>
      </div>
      <details className="small why">
        <summary>Why this score</summary>
        <ul>
          {entry.explanation.map((line) => (
            <li key={line} className="mono">{line}</li>
          ))}
        </ul>
        <div className="draft">
          <div className="small">
            Drafted action · <b>{entry.draft.channel}</b> ·{" "}
            <b className="gate">pending human approval</b> · never auto-sent
          </div>
          <div className="small" style={{ marginTop: 6 }}>
            <b>{entry.draft.title}</b>
          </div>
          <pre className="small draft-body" style={{ whiteSpace: "pre-wrap" }}>
            {entry.draft.script}
          </pre>
          <div className="small muted">Next step: {entry.draft.cta}</div>
          <div className="action-row">
            {state === "pending" ? (
              <>
                <button className="btn" onClick={() => onAction("approved")}>
                  Approve
                </button>
                <button className="btn" onClick={() => onAction("dismissed")}>
                  Dismiss
                </button>
              </>
            ) : (
              <span
                className={`pill ${state === "approved" ? "ok" : "neutral"}`}
              >
                {state === "approved" ? "Approved (local only)" : "Dismissed (local only)"}
              </span>
            )}
          </div>
          <p className="muted small" style={{ margin: "8px 0 0" }}>
            Nothing is ever sent: every action needs a human. Approve and
            Dismiss only change what you see here.
          </p>
        </div>
      </details>
    </div>
  );
}

/** Rescue board: appointments ranked by risk score, highest first. */
export default function BoardView() {
  const [states, setStates] = useState<Record<string, ActionState>>({});
  const ranked = rescueQueue
    .map((entry, i) => ({ entry, i }))
    .sort((a, b) =>
      b.entry.score !== a.entry.score
        ? b.entry.score - a.entry.score
        : SEGMENT_ORDER[a.entry.segment] - SEGMENT_ORDER[b.entry.segment],
    );

  return (
    <div>
      <div className="stat-grid">
        <div className="stat">
          <div className="stat-num">{summary.n_appointments}</div>
          <div className="stat-label">appointments this week</div>
        </div>
        <div className="stat">
          <div className="stat-num">{fmtPct(summary.pct_high_risk)}</div>
          <div className="stat-label">high-risk (CRITICAL + ELEVATED)</div>
        </div>
        <div className="stat">
          <div className="stat-num">{fmtUSD(summary.at_risk_revenue)}</div>
          <div className="stat-label">at-risk revenue</div>
        </div>
        <div className="stat">
          <div className="stat-num">{fmtUSD(summary.scheduled_revenue)}</div>
          <div className="stat-label">scheduled revenue</div>
        </div>
        <div className="stat">
          <div className="stat-num">{fmtUSD(summary.expected_noshow_loss)}</div>
          <div className="stat-label">expected no-show loss</div>
        </div>
      </div>

      <p className="muted small">
        Ranked by no-show risk score, highest first. CRITICAL means call
        today; ELEVATED means confirmation SMS; LOW means routine reminder.
        Nothing is ever sent: every action needs a human.
      </p>

      {ranked.map(({ entry, i }) => (
        <RescueCard
          key={`${entry.patient}-${i}`}
          entry={entry}
          state={states[`${entry.patient}-${i}`] ?? "pending"}
          onAction={(s) =>
            setStates((prev) => ({ ...prev, [`${entry.patient}-${i}`]: s }))
          }
        />
      ))}

      <p className="muted small">
        {summary.actions_sent} actions sent · {summary.actions_pending_human}{" "}
        pending human review. Week of {summary.week_of}.
      </p>
    </div>
  );
}
