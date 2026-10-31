import { useState } from "react";
import { draftAction, explain, scoreAppointment } from "../rules";
import type { Appointment } from "../types";
import { ScoreBar, SegmentBadge } from "./shared";

const EXAMPLE = `{
  "patient": "Jordan Lee",
  "visit_type": "New patient intake",
  "fee": 140,
  "scheduled_day": "2026-10-05",
  "appointment_day": "2026-11-04",
  "appointment_time": "09:00",
  "age": 22,
  "gender": "M",
  "scholarship": true,
  "sms_received": true,
  "neighbourhood": "Distillery District",
  "hotspot": false
}`;

/** Paste-an-appointment: the same rules run in the browser, no server, no LLM. */
export default function PasteView() {
  const [text, setText] = useState(EXAMPLE);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    appt: Appointment;
    score: number;
    prob: number;
    segment: "CRITICAL" | "ELEVATED" | "LOW";
    lines: string[];
    draft: ReturnType<typeof draftAction>;
  } | null>(null);

  function scoreIt() {
    setError(null);
    setResult(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      setError("That is not valid JSON. Check commas, quotes, and brackets.");
      return;
    }
    const appt = parsed as Appointment;
    for (const field of ["scheduled_day", "appointment_day", "age"] as const) {
      if (appt[field] === undefined || appt[field] === null || appt[field] === "") {
        setError(`Missing required field: ${field}.`);
        return;
      }
    }
    const scored = scoreAppointment(appt);
    setResult({
      appt,
      score: scored.score,
      prob: scored.prob,
      segment: scored.segment,
      lines: explain(scored),
      draft: draftAction(scored.segment, appt),
    });
  }

  return (
    <div className="card">
      <h2>Paste an appointment: the same rules, in your browser</h2>
      <p className="muted small">
        The TypeScript mirror of the Python engine runs here directly, no
        server and no LLM. Paste one appointment as JSON, then press Score it.
        Required fields: scheduled_day, appointment_day, age. Everything else
        has a safe default.
      </p>
      <label className="block-label">
        Appointment JSON
        <textarea
          className="input textarea"
          rows={14}
          value={text}
          onChange={(e) => setText(e.target.value)}
          spellCheck={false}
        />
      </label>
      <button className="btn primary" onClick={scoreIt}>
        Score it
      </button>
      {error && <div className="card error" style={{ marginTop: 12 }}>{error}</div>}
      {result && (
        <div style={{ marginTop: 16 }}>
          <div className="lead-head">
            <div>
              <b>{result.appt.patient || "patient"}</b>
              <span className="muted small">
                {" "}· {result.appt.visit_type || "appointment"} ·{" "}
                {result.appt.appointment_day} {result.appt.appointment_time || ""}
              </span>
            </div>
            <SegmentBadge segment={result.segment} />
          </div>
          <div className="bar-row">
            <span className="bar-label">No-show risk</span>
            <ScoreBar score={result.score} segment={result.segment} />
            <span className="bar-value">
              predicted probability{" "}
              <b className="mono">{(result.prob * 100).toFixed(1)}%</b>
            </span>
          </div>
          <h3>Factor breakdown</h3>
          <ul className="small">
            {result.lines.map((line) => (
              <li key={line} className="mono">{line}</li>
            ))}
          </ul>
          <div className="draft">
            <div className="small">
              Drafted action · <b>{result.draft.channel}</b> ·{" "}
              <b className="gate">pending human approval</b> · never auto-sent
            </div>
            <div className="small" style={{ marginTop: 6 }}>
              <b>{result.draft.title}</b>
            </div>
            <pre className="small draft-body" style={{ whiteSpace: "pre-wrap" }}>
              {result.draft.script}
            </pre>
            <div className="small muted">Next step: {result.draft.cta}</div>
          </div>
          <p className="muted small">
            Nothing is ever sent: every action needs a human. This page cannot
            contact patients or write to any system.
          </p>
        </div>
      )}
    </div>
  );
}
