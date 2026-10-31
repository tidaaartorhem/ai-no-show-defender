"""Build pipeline for NoShowShield.

1. Fetch the Kaggle Medical Appointment No Shows corpus (or reuse data/raw/).
2. Fit the additive-logit risk tables -> data/risk_tables.json.
3. Seed the fictional demo clinic book (week of Mon 2026-11-02).
4. Run the LangGraph pipeline -> data/outputs/{book,rescue,summary}.json.
5. Emit data/test-vectors.json, the exact Python<->TS scoring contract.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DATA = ROOT / "data"
RAW = DATA / "raw" / "noshowappointments-kagglev2-may-2016.csv"
OUT = DATA / "outputs"

CSV_URL = (
    "https://raw.githubusercontent.com/ShivankYadav/No-show/master/"
    "noshowappointments-kagglev2-may-2016.csv"
)

sys.path.insert(0, str(SRC))
from noshowshield import run_book  # noqa: E402
from noshowshield import rules  # noqa: E402

CLINIC = "Lakeshore Family Clinic"
CITY = "Toronto"


def fetch_corpus() -> Path:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    if not RAW.exists():
        print("downloading corpus ...")
        urllib.request.urlretrieve(CSV_URL, RAW)
    print("corpus:", RAW, RAW.stat().st_size, "bytes")
    return RAW


# ---------------------------------------------------------------- features ---

def lead_days(r: dict) -> int:
    s = datetime.fromisoformat(r["ScheduledDay"].replace("Z", "+00:00"))
    a = datetime.fromisoformat(r["AppointmentDay"].replace("Z", "+00:00"))
    return (a - s).days


def age_band(a: int) -> str:
    if a < 18:
        return "0-17"
    if a < 30:
        return "18-29"
    if a < 60:
        return "30-59"
    return "60+"


def corpus_feats(r: dict) -> dict:
    d = lead_days(r)
    lb = (
        "same_day" if d <= 0 else "1d" if d == 1 else "2-3d" if d <= 3
        else "4-7d" if d <= 7 else "8-14d" if d <= 14 else "15-30d" if d <= 30
        else "31d+"
    )
    return {
        "lead_age": f"{lb}|{age_band(int(r['Age']))}",
        "sch": "y" if r["Scholarship"] == "1" else "n",
        "sms": "y" if r["SMS_received"] == "1" else "n",
        "gen": r["Gender"],
        "dow": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][
            datetime.fromisoformat(r["AppointmentDay"].replace("Z", "+00:00")).weekday()
        ],
    }


def holdout(r: dict) -> bool:
    return int(hashlib.md5(r["AppointmentID"].encode()).hexdigest(), 16) % 5 == 0


def fit_tables(csv_path: Path) -> dict:
    rows = []
    with open(csv_path, newline="") as f:
        for r in csv.DictReader(f):
            if int(r["Age"]) < 0:  # 1 corrupt row
                continue
            rows.append(r)
    train = [r for r in rows if not holdout(r)]
    test = [r for r in rows if holdout(r)]
    p0 = sum(1 for r in train if r["No-show"] == "Yes") / len(train)
    L0 = math.log(p0 / (1 - p0))
    features: dict = {}
    for feat in ("lead_age", "sch", "sms", "gen", "dow"):
        agg: dict = defaultdict(lambda: [0, 0])
        for r in train:
            v = corpus_feats(r)[feat]
            a = agg[v]
            a[1] += 1
            a[0] += r["No-show"] == "Yes"
        features[feat] = {}
        for v, (ns, n) in agg.items():
            p = min(max(ns / n, 1e-6), 1 - 1e-6)
            features[feat][v] = {
                "rate": round(ns / n, 4),
                "n": n,
                "w": round(math.log(p / (1 - p)) - L0, 4),
            }

    def prob_of(feat: dict) -> float:
        s = L0 + sum(features[k].get(v, {"w": 0.0})["w"] for k, v in feat.items())
        return 1.0 / (1.0 + math.exp(-s))

    p99 = sorted(prob_of(corpus_feats(r)) for r in train)[int(0.99 * len(train))]

    def score_of(feat: dict) -> int:
        return min(100, int(math.floor(100.0 * prob_of(feat) / p99 + 0.5)))

    def seg(s: int) -> str:
        return "CRITICAL" if s >= 85 else ("ELEVATED" if s >= 55 else "LOW")

    cal = defaultdict(lambda: [0, 0])
    for r in test:
        g = seg(score_of(corpus_feats(r)))
        a = cal[g]
        a[1] += 1
        a[0] += r["No-show"] == "Yes"
    calibration = {
        g: {"observed_rate": round(cal[g][0] / cal[g][1], 4), "n": cal[g][1],
            "share": round(cal[g][1] / len(test), 3)}
        for g in ("CRITICAL", "ELEVATED", "LOW")
    }
    return {
        "meta": {
            "source": "Kaggle Medical Appointment No Shows (Joni Hoppen/Aquarela Analytics, 2016)",
            "corpus_n": len(rows),
            "train_n": len(train),
            "test_n": len(test),
            "baseline_logit": round(L0, 4),
            "baseline_p": round(p0, 4),
            "p99": round(p99, 6),
            "model": (
                "additive logit on measured log-odds weights per (lead_time x age_band) cell "
                "+ scholarship + sms_received + gender + weekday; "
                "score = min(100, floor(100*p/p99 + 0.5)); clinic hotspot prior adds +0.35 logit"
            ),
            "segments": {
                "CRITICAL": ">=85 (call today: confirm/deposit or release slot)",
                "ELEVATED": "55-84 (SMS confirmation campaign)",
                "LOW": "<55 (routine reminder)",
            },
            "excluded_rows": "1 row with Age=-1",
            "sunday_note": "no Sunday rows in corpus; Sunday weight defaults to 0",
            "calibration_holdout": calibration,
            "calibration_note": (
                "80/20 deterministic split by AppointmentID hash; weights fit on 80%, "
                "observed no-show rates measured on the 20% hold-out."
            ),
        },
        "features": features,
    }


# --------------------------------------------------------------- demo book ---

VISIT_FEES = {
    "Specialist consult": 220,
    "Procedure": 310,
    "Follow-up": 95,
    "New patient intake": 140,
    "Screening": 120,
    "Minor procedure": 420,
}

# Fictional patients for the seeded demo book of Lakeshore Family Clinic.
BOOK = [
    ("Daniel Okafor", "Specialist consult", "2026-10-14", "2026-11-02", "09:30", 24, "M", False, True, "Harbourfront", True),
    ("Priya Nair", "Follow-up", "2026-11-01", "2026-11-02", "10:15", 67, "F", False, False, "Liberty Village", False),
    ("Marcus Chen", "Procedure", "2026-09-28", "2026-11-03", "11:00", 31, "M", True, True, "Harbourfront", True),
    ("Sofia Rossi", "Screening", "2026-11-02", "2026-11-03", "13:45", 45, "F", False, False, "CityPlace", False),
    ("James Adeyemi", "New patient intake", "2026-10-05", "2026-11-04", "09:00", 22, "M", True, True, "Distillery District", False),
    ("Emma Kowalski", "Follow-up", "2026-11-03", "2026-11-04", "10:30", 58, "F", False, False, "Fort York", False),
    ("Liam Tremblay", "Procedure", "2026-10-20", "2026-11-05", "14:00", 19, "M", False, True, "Harbourfront", True),
    ("Aisha Khan", "Specialist consult", "2026-11-04", "2026-11-05", "15:30", 36, "F", False, False, "Queen West", False),
    ("Noah Patel", "Minor procedure", "2026-10-30", "2026-11-06", "08:30", 71, "M", False, False, "Liberty Village", False),
    ("Olivia Dubois", "Screening", "2026-09-15", "2026-11-06", "10:00", 27, "F", True, True, "Harbourfront", True),
    ("Ethan Wright", "Follow-up", "2026-11-02", "2026-11-02", "16:00", 41, "M", False, False, "CityPlace", False),
    ("Ava Mensah", "New patient intake", "2026-10-26", "2026-11-04", "11:30", 33, "F", False, True, "Fort York", False),
    ("Lucas Silva", "Procedure", "2026-11-05", "2026-11-05", "09:45", 52, "M", False, False, "Distillery District", False),
    ("Mia Fontaine", "Specialist consult", "2026-10-12", "2026-11-06", "13:15", 16, "F", False, True, "Queen West", False),
]


def seed_book() -> list[dict]:
    appts = []
    for (patient, visit, sched, day, time, age, gender, sch, sms, nbh, hotspot) in BOOK:
        appts.append(
            {
                "patient": patient,
                "visit_type": visit,
                "fee": VISIT_FEES[visit],
                "scheduled_day": sched,
                "appointment_day": day,
                "appointment_time": time,
                "age": age,
                "gender": gender,
                "scholarship": sch,
                "sms_received": sms,
                "neighbourhood": nbh,
                "hotspot": hotspot,
            }
        )
    return appts


# ----------------------------------------------------------- test vectors ---

VECTOR_DEFS = [
    # (label, appointment dict) — expected score/segment computed by the engine.
    ("critical_long_lead_young_hotspot", {"patient": "V1", "visit_type": "Procedure", "fee": 310,
        "scheduled_day": "2026-09-20", "appointment_day": "2026-11-04", "appointment_time": "10:00",
        "age": 23, "gender": "M", "scholarship": True, "sms_received": True,
        "neighbourhood": "Harbourfront", "hotspot": True}),
    ("elevated_mid", {"patient": "V2", "visit_type": "Follow-up", "fee": 95,
        "scheduled_day": "2026-10-25", "appointment_day": "2026-11-04", "appointment_time": "11:00",
        "age": 33, "gender": "F", "scholarship": False, "sms_received": True,
        "neighbourhood": "Fort York", "hotspot": False}),
    ("low_same_day_senior", {"patient": "V3", "visit_type": "Follow-up", "fee": 95,
        "scheduled_day": "2026-11-04", "appointment_day": "2026-11-04", "appointment_time": "15:00",
        "age": 68, "gender": "F", "scholarship": False, "sms_received": False,
        "neighbourhood": "Liberty Village", "hotspot": False}),
    ("low_same_day_child", {"patient": "V4", "visit_type": "Screening", "fee": 120,
        "scheduled_day": "2026-11-03", "appointment_day": "2026-11-03", "appointment_time": "09:00",
        "age": 8, "gender": "M", "scholarship": False, "sms_received": False,
        "neighbourhood": "CityPlace", "hotspot": False}),
    ("elevated_scholarship_sms", {"patient": "V5", "visit_type": "New patient intake", "fee": 140,
        "scheduled_day": "2026-10-15", "appointment_day": "2026-11-05", "appointment_time": "13:00",
        "age": 41, "gender": "F", "scholarship": True, "sms_received": True,
        "neighbourhood": "Queen West", "hotspot": False}),
    ("boundary_lead_31d", {"patient": "V6", "visit_type": "Specialist consult", "fee": 220,
        "scheduled_day": "2026-10-04", "appointment_day": "2026-11-04", "appointment_time": "10:30",
        "age": 55, "gender": "M", "scholarship": False, "sms_received": False,
        "neighbourhood": "Distillery District", "hotspot": False}),
    ("hotspot_on_vs_off", {"patient": "V7", "visit_type": "Procedure", "fee": 310,
        "scheduled_day": "2026-10-20", "appointment_day": "2026-11-05", "appointment_time": "14:30",
        "age": 29, "gender": "F", "scholarship": False, "sms_received": True,
        "neighbourhood": "Harbourfront", "hotspot": True}),
    ("sunday_defaults_zero", {"patient": "V8", "visit_type": "Follow-up", "fee": 95,
        "scheduled_day": "2026-10-30", "appointment_day": "2026-11-01", "appointment_time": "10:00",
        "age": 47, "gender": "F", "scholarship": False, "sms_received": False,
        "neighbourhood": "Liberty Village", "hotspot": False}),
    ("age_zero_band", {"patient": "V9", "visit_type": "Screening", "fee": 120,
        "scheduled_day": "2026-11-02", "appointment_day": "2026-11-03", "appointment_time": "09:30",
        "age": 0, "gender": "M", "scholarship": False, "sms_received": False,
        "neighbourhood": "CityPlace", "hotspot": False}),
    ("unknown_neighbourhood", {"patient": "V10", "visit_type": "Follow-up", "fee": 95,
        "scheduled_day": "2026-10-28", "appointment_day": "2026-11-06", "appointment_time": "16:30",
        "age": 62, "gender": "M", "scholarship": False, "sms_received": True,
        "neighbourhood": "Somewhere Else", "hotspot": False}),
    ("one_day_lead", {"patient": "V11", "visit_type": "Specialist consult", "fee": 220,
        "scheduled_day": "2026-11-04", "appointment_day": "2026-11-05", "appointment_time": "08:30",
        "age": 26, "gender": "F", "scholarship": False, "sms_received": False,
        "neighbourhood": "Fort York", "hotspot": False}),
    ("friday_long_lead", {"patient": "V12", "visit_type": "Minor procedure", "fee": 420,
        "scheduled_day": "2026-09-25", "appointment_day": "2026-11-06", "appointment_time": "08:00",
        "age": 37, "gender": "M", "scholarship": True, "sms_received": True,
        "neighbourhood": "Harbourfront", "hotspot": True}),
]


def build_vectors(tables: dict) -> list[dict]:
    vectors = []
    for label, appt in VECTOR_DEFS:
        s = rules.score_appointment(appt, tables)
        # Guard: raw 100*p/p99 must not sit on a rounding knife-edge, so the
        # TypeScript mirror (IEEE-754, same op order) agrees exactly.
        raw = 100.0 * s["prob"] / tables["meta"]["p99"]
        knife = abs(raw - round(raw)) < 1e-6 and abs(raw - math.floor(raw) - 0.5) < 1e-6
        if knife:
            raise RuntimeError(f"vector {label} sits on a rounding boundary; adjust it")
        if abs(raw - (math.floor(raw) + 0.5)) < 1e-6:
            raise RuntimeError(f"vector {label} on .5 boundary; adjust it")
        vectors.append(
            {
                "label": label,
                "appointment": appt,
                "expected": {
                    "score": s["score"],
                    "segment": s["segment"],
                    "prob": s["prob"],
                    "features": s["features"],
                },
            }
        )
    return vectors


def main() -> None:
    csv_path = fetch_corpus()
    tables = fit_tables(csv_path)
    (DATA / "risk_tables.json").write_text(json.dumps(tables, indent=1))
    print("risk_tables.json written; CRITICAL cal: %.4f, ELEVATED cal: %.4f, LOW cal: %.4f" % (
        tables["meta"]["calibration_holdout"]["CRITICAL"]["observed_rate"],
        tables["meta"]["calibration_holdout"]["ELEVATED"]["observed_rate"],
        tables["meta"]["calibration_holdout"]["LOW"]["observed_rate"],
    ))

    book = seed_book()
    result = run_book(book)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "book.json").write_text(json.dumps(
        {"clinic": CLINIC, "city": CITY, "week_of": "2026-11-02",
         "note": "Seeded fictional demo book; names and schedules are invented.",
         "appointments": book}, indent=1))
    (OUT / "rescue.json").write_text(json.dumps(result["rescue"], indent=1))
    (OUT / "summary.json").write_text(json.dumps(
        {"clinic": CLINIC, "week_of": "2026-11-02", **result["summary"]}, indent=1))
    print("summary:", json.dumps(result["summary"], indent=1))

    vectors = build_vectors(tables)
    (DATA / "test-vectors.json").write_text(json.dumps(
        {"contract": "Python engine <-> TypeScript mirror scoring agreement; "
                     "both must return expected.score/segment/prob exactly.",
         "vectors": vectors}, indent=1))
    segs = {}
    for v in vectors:
        segs.setdefault(v["expected"]["segment"], []).append(v["label"])
    print("vectors:", len(vectors), {k: len(x) for k, x in segs.items()})


if __name__ == "__main__":
    main()
