"""StateGraph wiring for NoShowShield.

Uses langgraph's StateGraph when available; falls back to the same node order
as an explicit ordered pipeline (identical semantics) if langgraph is missing.
"""

from __future__ import annotations

from typing import Any, TypedDict

from . import nodes


class DeskState(TypedDict, total=False):
    appointments: list[dict]
    rejected: list[str]
    features: list[dict]
    scored: list[dict]
    segment_counts: dict[str, int]
    rescue: list[dict]
    summary: dict


_NODE_ORDER = [
    ("intake", nodes.intake),
    ("featurize", nodes.featurize),
    ("score", nodes.score),
    ("segment", nodes.segment),
    ("action", nodes.action),
    ("gate", nodes.gate),
]


def _sequential_pipeline(initial: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = dict(initial)
    for _, fn in _NODE_ORDER:
        state.update(fn(state))
    return state


def build_graph():
    """Compile the intake -> featurize -> score -> segment -> action -> gate graph."""
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:  # pragma: no cover - exercised only without langgraph
        return None
    graph = StateGraph(DeskState)
    for name, fn in _NODE_ORDER:
        graph.add_node(name, fn)
    graph.set_entry_point("intake")
    graph.add_edge("intake", "featurize")
    graph.add_edge("featurize", "score")
    graph.add_edge("score", "segment")
    graph.add_edge("segment", "action")
    graph.add_edge("action", "gate")
    graph.add_edge("gate", END)
    return graph.compile()


def run_book(appointments: list[dict]) -> dict[str, Any]:
    """Run the full rescue-desk pipeline over one appointment book."""
    compiled = build_graph()
    if compiled is None:
        return _sequential_pipeline({"appointments": appointments})
    return compiled.invoke({"appointments": appointments})
