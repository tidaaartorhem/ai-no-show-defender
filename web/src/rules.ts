/** TypeScript mirror of src/noshowshield/rules.py - must agree exactly.
 *
 * Additive logit over measured log-odds weights. IEEE 754 doubles evaluate
 * identically to Python's, and the one deliberate rounding choice (half-up
 * via floor(x + 0.5), matching Python's math.floor(x + 0.5)) is shared.
 * The shared contract is data/test-vectors.json, asserted by both pytest
 * and vitest. Zero LLM calls anywhere in this pipeline.
 */
import riskTablesRaw from "./risk_tables.json";
import type {
  Appointment,
  Contribution,
  DraftAction,
  FeatureVector,
  RiskTables,
  ScoredAppointment,
  Segment,
} from "./types";

export const tables: RiskTables = riskTablesRaw as RiskTables;

export const CRITICAL_MIN = 85;
export const ELEVATED_MIN = 55;

// Clinic-configured catchment prior (see README-data.md in the repo root).
export const HOTSPOT_PRIOR_LOGIT = 0.35;

/** Days since 1970-01-01 for a civil date, timezone-free (Howard Hinnant). */
function daysFromCivil(y: number, m: number, d: number): number {
  const Y = y - (m <= 2 ? 1 : 0);
  const era = Math.floor((Y >= 0 ? Y : Y - 399) / 400);
  const yoe = Y - era * 400;
  const mp = m > 2 ? m - 3 : m + 9;
  const doy = Math.floor((153 * mp + 2) / 5) + d - 1;
  const doe = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
  return era * 146097 + doe - 719468;
}

/** Mirror of Python's date.fromisoformat(value[:10]); returns the day count. */
export function parseDay(value: string): number {
  const s = value.slice(0, 10);
  return daysFromCivil(
    Number(s.slice(0, 4)),
    Number(s.slice(5, 7)),
    Number(s.slice(8, 10)),
  );
}

/** Whole-day lead time, date-only, mirroring (appt_day - sched_day).days. */
export function leadDays(scheduledDay: string, appointmentDay: string): number {
  return parseDay(appointmentDay) - parseDay(scheduledDay);
}

export function leadBucket(leadDaysValue: number): string {
  if (leadDaysValue <= 0) return "same_day";
  if (leadDaysValue === 1) return "1d";
  if (leadDaysValue <= 3) return "2-3d";
  if (leadDaysValue <= 7) return "4-7d";
  if (leadDaysValue <= 14) return "8-14d";
  if (leadDaysValue <= 30) return "15-30d";
  return "31d+";
}

export function ageBand(age: number): string {
  const a = Math.max(0, Math.trunc(age));
  if (a < 18) return "0-17";
  if (a < 30) return "18-29";
  if (a < 60) return "30-59";
  return "60+";
}

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function featurize(appt: Appointment): FeatureVector {
  const dayNum = parseDay(appt.appointment_day);
  // 1970-01-01 was a Thursday (index 3); positive modulo keeps it safe.
  const weekday = (((dayNum + 3) % 7) + 7) % 7;
  return {
    lead_age: `${leadBucket(leadDays(appt.scheduled_day, appt.appointment_day))}|${ageBand(appt.age)}`,
    sch: appt.scholarship ? "y" : "n",
    sms: appt.sms_received ? "y" : "n",
    gen: String(appt.gender ?? "").toUpperCase().startsWith("M") ? "M" : "F",
    dow: DOW[weekday],
  };
}

function weight(feature: string, value: string): number {
  const f = tables.features[feature];
  if (!f) return 0;
  const entry = f[value];
  return entry ? entry.w : 0;
}

export function segmentOf(score: number): Segment {
  if (score >= CRITICAL_MIN) return "CRITICAL";
  if (score >= ELEVATED_MIN) return "ELEVATED";
  return "LOW";
}

/** Score one appointment: score, prob, segment, features, contributions. */
export function scoreAppointment(appt: Appointment): ScoredAppointment {
  const meta = tables.meta;
  const feats = featurize(appt);
  const contributions: Contribution[] = [];
  let logit = meta.baseline_logit;
  const keys: (keyof FeatureVector)[] = ["lead_age", "sch", "sms", "gen", "dow"];
  for (const feature of keys) {
    const w = weight(feature, feats[feature]);
    logit += w;
    contributions.push({
      feature,
      value: feats[feature],
      weight: Math.round(w * 10000) / 10000,
      direction:
        w > 0.005 ? "raises risk" : w < -0.005 ? "lowers risk" : "neutral",
    });
  }
  if (appt.hotspot) {
    logit += HOTSPOT_PRIOR_LOGIT;
    contributions.push({
      feature: "hotspot",
      value: appt.neighbourhood || "catchment hotspot",
      weight: HOTSPOT_PRIOR_LOGIT,
      direction: "raises risk",
    });
  }
  const prob = 1 / (1 + Math.exp(-logit));
  // Half-up rounding, mirroring Python's math.floor(x + 0.5).
  const score = Math.min(100, Math.floor((100 * prob) / meta.p99 + 0.5));
  return {
    score,
    prob: Math.round(prob * 10000) / 10000,
    segment: segmentOf(score),
    features: feats,
    contributions,
  };
}

/** Human-gated action drafts. Nothing is ever sent by the engine. */
export function draftAction(segment: Segment, appt: Appointment): DraftAction {
  const patient = appt.patient || "patient";
  const visit = appt.visit_type || "appointment";
  const day = appt.appointment_day || "";
  const time = appt.appointment_time || "";
  if (segment === "CRITICAL") {
    return {
      channel: "PHONE CALL",
      title: `Call ${patient} today`,
      script:
        `Hi ${patient}, this is Lakeshore Family Clinic confirming your ${visit} ` +
        `on ${day} at ${time}. We need a quick confirmation today so we can hold ` +
        `your slot. If we can't reach you, we may release the slot to the waitlist.`,
      cta: "Confirm / take deposit / release slot to waitlist",
      status: "pending_human",
    };
  }
  if (segment === "ELEVATED") {
    return {
      channel: "SMS",
      title: `Confirmation SMS for ${patient}`,
      script:
        `Lakeshore Family Clinic: Hi ${patient}, please reply YES to confirm your ` +
        `${visit} on ${day} at ${time}, or call us to reschedule. Thank you!`,
      cta: "Approve to queue in SMS batch",
      status: "pending_human",
    };
  }
  return {
    channel: "ROUTINE",
    title: `Standard reminder for ${patient}`,
    script: `Reminder: ${visit} on ${day} at ${time}. Reply to reschedule.`,
    cta: "Include in routine reminder run",
    status: "pending_human",
  };
}

const FEATURE_LABELS: Record<string, string> = {
  lead_age: "booking lead time x age",
  sch: "subsidized-care flag",
  sms: "already got an automated SMS",
  gen: "gender",
  dow: "day of week",
  hotspot: "clinic catchment hotspot",
};

/** Top risk drivers in plain language, highest weight first. */
export function explain(scored: ScoredAppointment): string[] {
  return scored.contributions
    .slice()
    .sort((a, b) => b.weight - a.weight)
    .filter((c) => Math.abs(c.weight) >= 0.02)
    .map((c) => {
      const arrow = c.weight > 0 ? "+" : "";
      return `${FEATURE_LABELS[c.feature] ?? c.feature} (${c.value}): ${arrow}${c.weight.toFixed(2)} logit`;
    });
}
