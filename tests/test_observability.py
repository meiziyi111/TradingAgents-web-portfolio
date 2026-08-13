"""Tests for dependency-free run/span observability."""

import json

import pytest

from tradingagents.dataflows.provenance import get_tool_trace, record_tool_trace, reset_tool_trace
from tradingagents.observability import (
    finish_trace,
    start_trace,
    trace_span,
    traced_node,
    write_trace,
)
from tradingagents.report_artifacts import build_decision_artifact


def test_nested_spans_keep_parent_child_relationship():
    run_id = start_trace(run_id="run-test", attributes={"ticker": "NVDA"})
    with trace_span("Research Manager", "graph_node") as parent_id:
        with trace_span("Portfolio Manager", "graph_node") as child_id:
            pass
    trace = finish_trace("SUCCESS")

    assert run_id == "run-test"
    assert trace["status"] == "SUCCESS"
    spans = {span["span_id"]: span for span in trace["spans"]}
    assert spans[parent_id]["parent_span_id"] == trace["root_span_id"]
    assert spans[child_id]["parent_span_id"] == parent_id
    assert trace["summary"]["span_count"] == 2


def test_traced_node_records_error_and_reraises():
    start_trace(run_id="run-error")

    def broken_node(_state):
        raise ValueError("invalid proposal")

    with pytest.raises(ValueError, match="invalid proposal"):
        traced_node("Broken Node", broken_node)({"company_of_interest": "NVDA"})
    trace = finish_trace("ERROR", "ValueError: invalid proposal")

    assert trace["spans"][0]["name"] == "Broken Node"
    assert trace["spans"][0]["status"] == "ERROR"
    assert trace["spans"][0]["error_type"] == "ValueError"


def test_tool_provenance_is_linked_to_active_run_and_trace():
    start_trace(run_id="run-tools")
    reset_tool_trace()
    record_tool_trace({
        "tool": "get_stock_data",
        "vendor": "yfinance",
        "attempt": 1,
        "status": "SUCCESS",
        "requested_at": "2026-08-14T00:00:00+00:00",
        "completed_at": "2026-08-14T00:00:00.250000+00:00",
        "output_sha256": "abc123",
    })
    evidence = get_tool_trace()
    trace = finish_trace("SUCCESS")

    assert evidence[0]["run_id"] == "run-tools"
    assert evidence[0]["duration_ms"] == 250.0
    assert evidence[0]["span_id"] == trace["spans"][0]["span_id"]
    assert trace["spans"][0]["kind"] == "tool"


def test_trace_write_is_atomic_and_round_trips(tmp_path):
    start_trace(run_id="run-file")
    with trace_span("Hard Risk Engine", "graph_node"):
        pass
    trace = finish_trace("SUCCESS")
    path = write_trace(tmp_path / "trace.json", trace)

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["run_id"] == "run-file"
    assert loaded["spans"][0]["name"] == "Hard Risk Engine"
    assert not (tmp_path / "trace.json.tmp").exists()


def test_decision_artifact_carries_trace_linkage():
    artifact = build_decision_artifact(
        ticker="NVDA",
        trade_date="2026-08-14",
        decision_payload={
            "rating": "Hold",
            "executive_summary": "Wait for evidence.",
            "investment_thesis": "Insufficient catalyst confirmation.",
        },
        run_id="run-artifact",
        trace_summary={"span_count": 12},
        trace_file="trace_2026-08-14_run-artifact.json",
    )

    assert artifact["run_id"] == "run-artifact"
    assert artifact["trace_summary"]["span_count"] == 12
    assert artifact["trace_file"].endswith("run-artifact.json")
