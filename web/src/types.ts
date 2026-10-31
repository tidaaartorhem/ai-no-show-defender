export interface Appointment {
  patient: string;
  visit_type: string;
  fee: number;
  scheduled_day: string;
  appointment_day: string;
  appointment_time: string;
  age: number;
  gender: string;
  scholarship: boolean;
  sms_received: boolean;
  neighbourhood: string;
  hotspot: boolean;
}

export interface FeatureVector {
  lead_age: string;
  sch: string;
  sms: string;
  gen: string;
  dow: string;
}

export interface Contribution {
  feature: string;
  value: string;
  weight: number;
  direction: "raises risk" | "lowers risk" | "neutral";
}

export type Segment = "CRITICAL" | "ELEVATED" | "LOW";

export interface ScoredAppointment {
  score: number;
  prob: number;
  segment: Segment;
  features: FeatureVector;
  contributions: Contribution[];
}

export interface DraftAction {
  channel: string;
  title: string;
  script: string;
  cta: string;
  status: string;
}

export interface RiskTables {
  meta: {
    source: string;
    corpus_n: number;
    train_n: number;
    test_n: number;
    baseline_logit: number;
    baseline_p: number;
    p99: number;
    model: string;
    segments: Record<string, string>;
    excluded_rows: string;
    sunday_note: string;
    calibration_holdout: Record<string, { observed_rate: number; n: number; share: number }>;
    calibration_note: string;
  };
  features: Record<string, Record<string, { rate: number; n: number; w: number }>>;
}

export interface AppointmentBook {
  clinic: string;
  city: string;
  week_of: string;
  note: string;
  appointments: Appointment[];
}

export interface RescueEntry {
  patient: string;
  visit_type: string;
  appointment_day: string;
  appointment_time: string;
  fee: number;
  score: number;
  prob: number;
  segment: Segment;
  explanation: string[];
  draft: DraftAction;
}

export interface Summary {
  clinic: string;
  week_of: string;
  n_appointments: number;
  n_critical: number;
  n_elevated: number;
  n_low: number;
  pct_high_risk: number;
  scheduled_revenue: number;
  expected_noshow_loss: number;
  at_risk_revenue: number;
  actions_pending_human: number;
  actions_sent: number;
}

export interface TestVectors {
  contract: string;
  vectors: {
    label: string;
    appointment: Appointment;
    expected: {
      score: number;
      segment: Segment;
      prob: number;
      features: FeatureVector;
    };
  }[];
}
