"""LangGraph node functions for the NoShowShield pipeline.

Pipeline: intake -> featurize -> score -> segment -> action -> gate
Every node is pure and deterministic; there are zero LLM calls anywhere.
"""

from __future__ import annotations

from typing import Any

from . import rules
from .rules import draft_action, explain, score_appointment, segment_of


def intake(state: dict[str, Any]) -> dict[str, Any]:
    """Validate the incoming appointment book; drop malformed rows, keep a count."""
    book = state.get("appointments", [])
    valid, rejected = [], []
    required = ("patient", "scheduled_day", "appointment_day", "age")
    for appt in book:
        if all(appt.get(k) not in (None, "") for k in required):
            valid.append(appt)
        else:
            rejected.append(appt.get("patient", "?"))
    return {"appointments": valid, "rejected": rejected}


def featurize(state: dict[str, Any]) -> dict[str, Any]:
    return {"features": [rules.featurize(a) for a in state["appointments"]]}


def score(state: dict[str, Any]) -> dict[str, Any]:
    scored = []
    for appt in state["appointments"]:
        s = score_appointment(appt)
        s["appointment"] = appt
        s["explanation"] = explain(s)
        scored.append(s)
    return {"scored": scored}


def segment(state: dict[str, Any]) -> dict[str, Any]:
    counts = {"CRITICAL": 0, "ELEVATED": 0, "LOW": 0}
    for s in state["scored"]:
        counts[s["segment"]] += 1
    return {"segment_counts": counts}


def action(state: dict[str, Any]) -> dict[str, Any]:
    """Draft the human-gated rescue actions. Nothing is sent."""
    rescue = []
    for s in state["scored"]:
        rescue.append(
            {
                "patient": s["appointment"].get("patient"),
                "visit_type": s["appointment"].get("visit_type"),
                "appointment_day": s["appointment"].get("appointment_day"),
                "appointment_time": s["appointment"].get("appointment_time"),
                "fee": s["appointment"].get("fee", 0),
                "score": s["score"],
                "prob": s["prob"],
                "segment": s["segment"],
                "explanation": s["explanation"],
                "draft": draft_action(s["segment"], s["appointment"]),
            }
        )
    rescue.sort(key=lambda r: r["score"], reverse=True)
    return {"rescue": rescue}


def gate(state: dict[str, Any]) -> dict[str, Any]:
    """Final human gate: assemble the desk summary. All actions stay pending."""
    rescue = state["rescue"]
    total_fee = sum(r["fee"] for r in rescue)
    expected_loss = sum(r["fee"] * r["prob"] for r in rescue)
    high = [r for r in rescue if r["segment"] in ("CRITICAL", "ELEVATED")]
    return {
        "summary": {
            "n_appointments": len(rescue),
            "n_critical": sum(1 for r in rescue if r["segment"] == "CRITICAL"),
            "n_elevated": sum(1 for r in rescue if r["segment"] == "ELEVATED"),
            "n_low": sum(1 for r in rescue if r["segment"] == "LOW"),
            "pct_high_risk": round(100 * len(high) / len(rescue), 1) if rescue else 0.0,
            "scheduled_revenue": round(total_fee, 2),
            "expected_noshow_loss": round(expected_loss, 2),
            "at_risk_revenue": round(sum(r["fee"] for r in high), 2),
            "actions_pending_human": len(rescue),
            "actions_sent": 0,
        }
    }
