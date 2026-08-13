"""Regression tests for point-in-time-safe Agent memory."""

from unittest.mock import MagicMock, patch

import pandas as pd

from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.graph.trading_graph import TradingAgentsGraph


DECISION = "Rating: Buy\nUse a small, risk-controlled position."


def _log(tmp_path):
    return TradingMemoryLog({"memory_log_path": str(tmp_path / "memory.md")})


def _resolve(
    log,
    ticker,
    decision_date,
    available_at,
    reflection,
):
    log.store_decision(ticker, decision_date, DECISION)
    log.update_with_outcome(
        ticker,
        decision_date,
        raw_return=0.05,
        alpha_return=0.02,
        holding_days=5,
        reflection=reflection,
        outcome_observed_at=available_at,
        memory_available_at=available_at,
        reflection_created_at=f"{available_at}T08:00:00+00:00",
    )


def test_historical_replay_excludes_legacy_memory_with_unknown_availability(tmp_path):
    log = _log(tmp_path)
    log.store_decision("NVDA", "2026-01-05", DECISION)
    log.update_with_outcome("NVDA", "2026-01-05", 0.05, 0.02, 5, "Legacy lesson.")

    assert "Legacy lesson." in log.get_past_context("NVDA")
    assert log.get_past_context("NVDA", as_of_date="2026-02-01") == ""


def test_historical_replay_only_injects_memory_available_by_cutoff(tmp_path):
    log = _log(tmp_path)
    _resolve(log, "NVDA", "2026-01-01", "2026-01-10", "Early lesson.")
    _resolve(log, "NVDA", "2026-02-01", "2026-02-10", "Future lesson.")

    context = log.get_past_context("NVDA", as_of_date="2026-01-15")
    assert "Early lesson." in context
    assert "Future lesson." not in context


def test_pending_entry_on_or_after_run_date_is_not_resolved(tmp_path):
    log = _log(tmp_path)
    log.store_decision("NVDA", "2026-01-15", DECISION)
    graph = MagicMock(spec=TradingAgentsGraph)
    graph.memory_log = log
    graph._fetch_return_observation = MagicMock()

    TradingAgentsGraph._resolve_pending_entries(
        graph,
        "NVDA",
        as_of_date="2026-01-15",
    )

    graph._fetch_return_observation.assert_not_called()
    assert len(log.get_pending_entries()) == 1


def test_strict_observation_requires_full_holding_horizon():
    four_rows = pd.DataFrame(
        {"Close": [100.0, 101.0, 102.0, 103.0]},
        index=pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]),
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


def test_observation_reports_exact_outcome_date():
    six_rows = pd.DataFrame(
        {"Close": [100.0, 101.0, 102.0, 103.0, 104.0, 110.0]},
        index=pd.to_datetime(
            ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12"]
        ),
    )
    benchmark = pd.DataFrame(
        {"Close": [100.0, 100.0, 101.0, 101.0, 102.0, 105.0]},
        index=six_rows.index,
    )
    graph = MagicMock(spec=TradingAgentsGraph)

    with patch("tradingagents.graph.trading_graph.yf.Ticker") as ticker_cls:
        ticker_cls.side_effect = [
            MagicMock(history=MagicMock(return_value=six_rows)),
            MagicMock(history=MagicMock(return_value=benchmark)),
        ]
        raw, alpha, days, observed_at = TradingAgentsGraph._fetch_return_observation(
            graph,
            "NVDA",
            "2026-01-05",
            holding_days=5,
            as_of_date="2026-01-13",
            require_full_horizon=True,
        )

    assert raw == 0.10
    assert alpha == 0.05
    assert days == 5
    assert observed_at == "2026-01-12"
