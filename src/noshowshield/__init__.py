"""NoShowShield: deterministic no-show risk engine for SME clinics.

Zero hosted LLM calls. Every weight is a measured log-odds contribution from the
Kaggle Medical Appointment No Shows corpus (110,527 rows, Joni Hoppen /
Aquarela Analytics, 2016). See data/README-data.md and data/risk_tables.json.
"""

from .rules import (
    featurize,
    lead_bucket,
    age_band,
    score_appointment,
    segment_of,
    SEGMENTS,
    draft_action,
    explain,
)
from .graph import build_graph, run_book

__all__ = [
    "featurize",
    "lead_bucket",
    "age_band",
    "score_appointment",
    "segment_of",
    "SEGMENTS",
    "draft_action",
    "explain",
    "build_graph",
    "run_book",
]
