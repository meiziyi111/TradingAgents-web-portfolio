"""Offline smoke checks for point-in-time memory and basic observability."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pandas as pd

from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.dataflows.provenance import get_tool_trace, record_tool_trace, reset_tool_trace
from tradingagents.graph.propagation import Propagator
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.observability import (
    finish_trace,
    start_trace,
    trace_span,
    traced_node,
    write_trace,
)
from tradingagents.report_artifacts import build_decision_artifact


DECISION = "Rating: Buy\nUse a small, risk-controlled position."


def _resolved_memory(
    log: TradingMemoryLog,
    decision_date: str,
    available_at: str,
    lesson: str,
) -> None:
    log.store_decision("NVDA", decision_date, DECISION)
    log.update_with_outcome(
        "NVDA",
        decision_date,
        0.05,
        0.02,
        5,
        lesson,
        outcome_observed_at=available_at,
        memory_available_at=available_at,
        reflection_created_at=f"{available_at}T08:00:00+00:00",
    )


def main() -> None:
    passed: list[str] = []
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        log = TradingMemoryLog({"memory_log_path": str(root / "memory.md")})
        _resolved_memory(log, "2026-01-01", "2026-01-10", "Early lesson.")
        _resolved_memory(log, "2026-02-01", "2026-02-10", "Future lesson.")
        context = log.get_past_context("NVDA", as_of_date="2026-01-15")
        assert "Early lesson." in context and "Future lesson." not in context
        passed.append("memory_as_of_filter")

        legacy = TradingMemoryLog({"memory_log_path": str(root / "legacy.md")})
        legacy.store_decision("NVDA", "2026-01-01", DECISION)
        legacy.update_with_outcome("NVDA", "2026-01-01", 0.05, 0.02, 5, "Legacy.")
        assert legacy.get_past_context("NVDA")
        assert not legacy.get_past_context("NVDA", as_of_date="2026-03-01")
        passed.append("legacy_memory_fail_closed")

        pending = TradingMemoryLog({"memory_log_path": str(root / "pending.md")})
        pending.store_decision("NVDA", "2026-01-15", DECISION)
        graph = MagicMock(spec=TradingAgentsGraph)
        graph.memory_log = pending
        graph._fetch_return_observation = MagicMock()
        TradingAgentsGraph._resolve_pending_entries(
            graph, "NVDA", as_of_date="2026-01-15"
        )
        graph._fetch_return_observation.assert_not_called()
        passed.append("future_pending_not_resolved")

        four_rows = pd.DataFrame(
            {"Close": [100.0, 101.0, 102.0, 103.0]},
            index=pd.to_datetime(
                ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
            ),
        )
        graph = MagicMock(spec=TradingAgentsGraph)
        with patch("tradingagents.graph.trading_graph.yf.Ticker") as ticker_cls:
            ticker_cls.return_value.history.return_value = four_rows
            result = TradingAgentsGraph._fetch_return_observation(
                graph,
                "NVDA",
                "2026-01-05",
                holding_days=5,
                as_of_date="2026-01-09",
                require_full_horizon=True,
            )
        assert result == (None, None, None, None)
        passed.append("full_horizon_required")

        run_id = start_trace(run_id="smoke-run", attributes={"ticker": "NVDA"})
        reset_tool_trace()
        with trace_span("News Analyst", "graph_node") as analyst_span:
            record_tool_trace({
                "tool": "get_news",
                "vendor": "yfinance",
                "attempt": 1,
                "status": "SUCCESS",
                "requested_at": "2026-08-14T00:00:00+00:00",
                "completed_at": "2026-08-14T00:00:00.125000+00:00",
                "output_sha256": "abc123",
            })
        trace = finish_trace("SUCCESS")
        evidence = get_tool_trace()
        tool_span = next(span for span in trace["spans"] if span["kind"] == "tool")
        assert run_id == evidence[0]["run_id"] == "smoke-run"
        assert evidence[0]["duration_ms"] == 125.0
        assert tool_span["parent_span_id"] == analyst_span
        passed.append("tool_trace_linkage")

        start_trace(run_id="error-run")

        def broken(_state):
            raise ValueError("invalid proposal")

        try:
            traced_node("Broken Node", broken)({"company_of_interest": "NVDA"})
        except ValueError:
            pass
        error_trace = finish_trace("ERROR", "ValueError: invalid proposal")
        assert error_trace["spans"][0]["status"] == "ERROR"
        passed.append("node_error_trace")

        trace_path = write_trace(root / "trace.json", trace)
        assert json.loads(trace_path.read_text(encoding="utf-8"))["run_id"] == "smoke-run"
        assert not (root / "trace.json.tmp").exists()
        passed.append("trace_atomic_round_trip")

        artifact = build_decision_artifact(
            ticker="NVDA",
            trade_date="2026-08-14",
            decision_payload={
                "rating": "Hold",
                "executive_summary": "Wait for evidence.",
                "investment_thesis": "Insufficient catalyst confirmation.",
            },
            run_id="artifact-run",
            trace_summary={"span_count": 2},
            trace_file="trace_2026-08-14_artifact-run.json",
        )
        assert artifact["run_id"] == "artifact-run"
        passed.append("artifact_trace_linkage")

        state = Propagator().create_initial_state(
            "NVDA", "2026-08-14", run_id="state-run"
        )
        assert state["run_id"] == "state-run"
        passed.append("state_run_id")

        graph = object.__new__(TradingAgentsGraph)
        graph.config = {"results_dir": str(root)}
        graph.current_run_id = None
        graph.last_trace = {}
        graph.last_trace_path = None

        def fake_stream(_ticker, _date, **_kwargs):
            with trace_span("Hard Risk Engine", "graph_node"):
                yield {"run_id": graph.current_run_id, "final_decision_structured": {}}

        graph._stream_propagate_core = fake_stream
        chunks = list(
            TradingAgentsGraph.stream_propagate(
                graph,
                "NVDA",
                "2026-08-14",
            )
        )
        assert chunks[0]["run_id"] == graph.last_trace["run_id"]
        assert graph.last_trace["status"] == "SUCCESS"
        assert Path(graph.last_trace_path).exists()
        passed.append("stream_trace_persisted")

    print(f"Third-round smoke checks passed: {len(passed)}")
    print(", ".join(passed))


if __name__ == "__main__":
    main()
