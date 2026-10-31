"""Deterministic no-show risk rules.

Model: additive logit. For each appointment we featurize it, look up the
measured log-odds weight of each feature value, add them to the corpus baseline
logit, squash through the sigmoid to get a no-show probability p, then scale:

    score = min(100, round(100 * p / P99))

P99 is the 99th percentile of predicted p over the training corpus. So a score
of 100 means "predicted no-show probability at the top 1% of the corpus" and a
score of 50 means half that. This is a disclosed relative-risk index, not a
raw probability; per-segment calibration on a 20% hold-out is reported in
data/risk_tables.json and in the UI's Method tab.

The TypeScript mirror in web/src/rules.ts implements this exact algorithm; the
two are kept in agreement by data/test-vectors.json.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

SEGMENTS = ("CRITICAL", "ELEVATED", "LOW")

# CRITICAL >= 85: call today. ELEVATED 55-84: confirmation SMS campaign.
# LOW < 55: routine reminder. Thresholds tuned from the hold-out calibration.
CRITICAL_MIN = 85
ELEVATED_MIN = 55

HOTSPOT_PRIOR_LOGIT = 0.35  # clinic-configured catchment prior (see README-data.md)

_TABLES: dict | None = None


def load_tables(path: str | Path | None = None) -> dict:
    global _TABLES
    if _TABLES is not None and path is None:
        return _TABLES
    p = Path(path) if path else Path(__file__).resolve().parent.parent.parent / "data" / "risk_tables.json"
    tables = json.loads(p.read_text())
    if path is None:
        _TABLES = tables
    return tables


def lead_bucket(lead_days: int) -> str:
    if lead_days <= 0:
        return "same_day"
    if lead_days == 1:
        return "1d"
    if lead_days <= 3:
        return "2-3d"
    if lead_days <= 7:
        return "4-7d"
    if lead_days <= 14:
        return "8-14d"
    if lead_days <= 30:
        return "15-30d"
    return "31d+"


def age_band(age: int) -> str:
    a = max(0, int(age))
    if a < 18:
        return "0-17"
    if a < 30:
        return "18-29"
    if a < 60:
        return "30-59"
    return "60+"


def _parse_day(value: str) -> date:
    return date.fromisoformat(value[:10])


def lead_days(scheduled_day: str, appointment_day: str) -> int:
    return (_parse_day(appointment_day) - _parse_day(scheduled_day)).days


def featurize(appt: dict) -> dict:
    """Map an appointment record to the model's feature vector."""
    ld = lead_bucket(lead_days(appt["scheduled_day"], appt["appointment_day"]))
    return {
        "lead_age": f"{ld}|{age_band(appt['age'])}",
        "sch": "y" if appt.get("scholarship") else "n",
        "sms": "y" if appt.get("sms_received") else "n",
        "gen": "M" if str(appt.get("gender", "")).upper().startswith("M") else "F",
        "dow": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][
            _parse_day(appt["appointment_day"]).weekday()
        ],
    }


def _weight(tables: dict, feature: str, value: str) -> float:
    return float(tables["features"].get(feature, {}).get(value, {}).get("w", 0.0))


def score_appointment(appt: dict, tables: dict | None = None) -> dict:
    """Score one appointment. Returns score, prob, and per-feature contributions."""
    tables = tables or load_tables()
    meta = tables["meta"]
    feats = featurize(appt)
    contributions = []
    logit = float(meta["baseline_logit"])
    for feature, value in feats.items():
        w = _weight(tables, feature, value)
        logit += w
        contributions.append(
            {
                "feature": feature,
                "value": value,
                "weight": round(w, 4),
                "direction": "raises risk" if w > 0.005 else ("lowers risk" if w < -0.005 else "neutral"),
            }
        )
    hotspot = bool(appt.get("hotspot"))
    if hotspot:
        logit += HOTSPOT_PRIOR_LOGIT
        contributions.append(
            {
                "feature": "hotspot",
                "value": appt.get("neighbourhood", "catchment hotspot"),
                "weight": HOTSPOT_PRIOR_LOGIT,
                "direction": "raises risk",
            }
        )
    prob = 1.0 / (1.0 + math.exp(-logit))
    # Half-up rounding (matches JS Math.round); Python's round() is banker's.
    score = min(100, int(math.floor(100.0 * prob / float(meta["p99"]) + 0.5)))
    return {
        "score": score,
        "prob": round(prob, 4),
        "segment": segment_of(score),
        "features": feats,
        "contributions": contributions,
    }


def segment_of(score: int) -> str:
    if score >= CRITICAL_MIN:
        return "CRITICAL"
    if score >= ELEVATED_MIN:
        return "ELEVATED"
    return "LOW"


def draft_action(segment: str, appt: dict) -> dict:
    """Human-gated action drafts. Nothing is ever sent by the engine."""
    patient = appt.get("patient", "patient")
    visit = appt.get("visit_type", "appointment")
    day = appt.get("appointment_day", "")
    time = appt.get("appointment_time", "")
    if segment == "CRITICAL":
        return {
            "channel": "PHONE CALL",
            "title": f"Call {patient} today",
            "script": (
                f"Hi {patient}, this is Lakeshore Family Clinic confirming your {visit} "
                f"on {day} at {time}. We need a quick confirmation today so we can hold "
                f"your slot. If we can't reach you, we may release the slot to the waitlist."
            ),
            "cta": "Confirm / take deposit / release slot to waitlist",
            "status": "pending_human",
        }
    if segment == "ELEVATED":
        return {
            "channel": "SMS",
            "title": f"Confirmation SMS for {patient}",
            "script": (
                f"Lakeshore Family Clinic: Hi {patient}, please reply YES to confirm your "
                f"{visit} on {day} at {time}, or call us to reschedule. Thank you!"
            ),
            "cta": "Approve to queue in SMS batch",
            "status": "pending_human",
        }
    return {
        "channel": "ROUTINE",
        "title": f"Standard reminder for {patient}",
        "script": f"Reminder: {visit} on {day} at {time}. Reply to reschedule.",
        "cta": "Include in routine reminder run",
        "status": "pending_human",
    }


def explain(scored: dict) -> list[str]:
    """Top risk drivers in plain language, highest weight first."""
    drivers = sorted(scored["contributions"], key=lambda c: c["weight"], reverse=True)
    labels = {
        "lead_age": "booking lead time x age",
        "sch": "subsidized-care flag",
        "sms": "already got an automated SMS",
        "gen": "gender",
        "dow": "day of week",
        "hotspot": "clinic catchment hotspot",
    }
    lines = []
    for c in drivers:
        if abs(c["weight"]) < 0.02:
            continue
        arrow = "+" if c["weight"] > 0 else ""
        lines.append(
            f"{labels.get(c['feature'], c['feature'])} ({c['value']}): {arrow}{c['weight']:.2f} logit"
        )
    return lines
