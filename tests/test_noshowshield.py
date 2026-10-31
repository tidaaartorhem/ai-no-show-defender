"""pytest suite for NoShowShield. All deterministic; no network, no LLM."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from noshowshield import (  # noqa: E402
    age_band,
    build_graph,
    draft_action,
    explain,
    featurize,
    lead_bucket,
    run_book,
    score_appointment,
    segment_of,
)
from noshowshield import rules  # noqa: E402

TABLES = rules.load_tables()


def appt(**kw):
    base = {
        "patient": "Test Patient",
        "visit_type": "Follow-up",
        "fee": 95,
        "scheduled_day": "2026-10-25",
        "appointment_day": "2026-11-04",
        "appointment_time": "10:00",
        "age": 40,
        "gender": "F",
        "scholarship": False,
        "sms_received": False,
        "neighbourhood": "Fort York",
        "hotspot": False,
    }
    base.update(kw)
    return base


# ------------------------------------------------------------- buckets ---


def test_lead_bucket_boundaries():
    assert lead_bucket(0) == "same_day"
    assert lead_bucket(-3) == "same_day"
    assert lead_bucket(1) == "1d"
    assert lead_bucket(3) == "2-3d"
    assert lead_bucket(7) == "4-7d"
    assert lead_bucket(14) == "8-14d"
    assert lead_bucket(30) == "15-30d"
    assert lead_bucket(31) == "31d+"


def test_age_band_boundaries():
    assert age_band(0) == "0-17"
    assert age_band(17) == "0-17"
    assert age_band(18) == "18-29"
    assert age_band(29) == "18-29"
    assert age_band(30) == "30-59"
    assert age_band(59) == "30-59"
    assert age_band(60) == "60+"
    assert age_band(-1) == "0-17"  # clamped, never crashes


def test_featurize_shape():
    f = featurize(appt())
    assert set(f) == {"lead_age", "sch", "sms", "gen", "dow"}
    assert f["lead_age"] == "8-14d|30-59"
    assert f["dow"] == "Wed"  # 2026-11-04 is a Wednesday


def test_sunday_weight_defaults_to_zero():
    # 2026-11-01 is a Sunday; corpus has no Sunday rows.
    f = featurize(appt(appointment_day="2026-11-01"))
    assert f["dow"] == "Sun"
    assert "Sun" not in TABLES["features"]["dow"]
    s = score_appointment(appt(appointment_day="2026-11-01"))
    assert 0 <= s["score"] <= 100


# -------------------------------------------------------------- scoring ---


def test_score_bounds_and_determinism():
    s1 = score_appointment(appt())
    s2 = score_appointment(appt())
    assert s1 == s2
    assert 0 <= s1["score"] <= 100
    assert 0.0 <= s1["prob"] <= 1.0


def test_risk_ordering_same_day_vs_long_lead():
    low = score_appointment(appt(scheduled_day="2026-11-04", age=68))
    high = score_appointment(appt(scheduled_day="2026-09-20", age=23, hotspot=True))
    assert high["score"] > low["score"]


def test_hotspot_prior_adds_risk():
    a = appt(scheduled_day="2026-10-20", age=29, sms_received=True)
    off = score_appointment(dict(a, hotspot=False))
    on = score_appointment(dict(a, hotspot=True, neighbourhood="Harbourfront"))
    assert on["score"] > off["score"]
    assert any(c["feature"] == "hotspot" for c in on["contributions"])


def test_sms_paradox_is_honest():
    # Corpus-measured: sms_received=1 has a HIGHER observed no-show rate
    # (selection effect). The weight must be positive, not hand-tuned away.
    w = TABLES["features"]["sms"]["y"]["w"]
    assert w > 0, "sms weight must stay positive; the paradox is real data"
    a = appt(sms_received=False)
    b = appt(sms_received=True)
    assert score_appointment(b)["score"] >= score_appointment(a)["score"]


def test_segment_thresholds():
    assert segment_of(100) == "CRITICAL"
    assert segment_of(85) == "CRITICAL"
    assert segment_of(84) == "ELEVATED"
    assert segment_of(55) == "ELEVATED"
    assert segment_of(54) == "LOW"
    assert segment_of(0) == "LOW"


def test_explain_lists_drivers():
    s = score_appointment(appt(scheduled_day="2026-09-20", age=23, hotspot=True))
    lines = explain(s)
    assert lines, "expected at least one material driver"
    assert all("logit" in line for line in lines)


def test_draft_actions_are_human_gated():
    for seg in ("CRITICAL", "ELEVATED", "LOW"):
        d = draft_action(seg, appt())
        assert d["status"] == "pending_human"
        assert d["script"], "draft copy must be non-empty"
    assert draft_action("CRITICAL", appt())["channel"] == "PHONE CALL"
    assert draft_action("ELEVATED", appt())["channel"] == "SMS"


# ------------------------------------------------------- vector contract ---


def test_vectors_agree_with_engine():
    vectors = json.loads((ROOT / "data" / "test-vectors.json").read_text())["vectors"]
    assert len(vectors) >= 10
    seen = set()
    for v in vectors:
        s = score_appointment(v["appointment"])
        exp = v["expected"]
        assert s["score"] == exp["score"], v["label"]
        assert s["segment"] == exp["segment"], v["label"]
        assert s["prob"] == exp["prob"], v["label"]
        assert s["features"] == exp["features"], v["label"]
        seen.add(exp["segment"])
    assert seen == {"CRITICAL", "ELEVATED", "LOW"}, "vectors must cover all segments"


# -------------------------------------------------------------- graph ---


def test_graph_compiles_to_langgraph():
    compiled = build_graph()
    assert compiled is not None, "langgraph must be installed for this build"


def test_run_book_end_to_end():
    book = json.loads((ROOT / "data" / "outputs" / "book.json").read_text())["appointments"]
    result = run_book(book)
    assert result["summary"]["n_appointments"] == len(book)
    assert result["summary"]["actions_sent"] == 0
    assert result["summary"]["actions_pending_human"] == len(book)
    scores = [r["score"] for r in result["rescue"]]
    assert scores == sorted(scores, reverse=True), "rescue list must be risk-sorted"
    for r in result["rescue"]:
        assert r["draft"]["status"] == "pending_human"


def test_intake_rejects_malformed_rows():
    result = run_book([appt(), {"patient": "Broken"}])
    assert result["rejected"] == ["Broken"]
    assert result["summary"]["n_appointments"] == 1
