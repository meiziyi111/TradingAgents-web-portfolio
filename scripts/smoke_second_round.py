"""Offline smoke checks for the second-round decision/risk redesign.

Runs without pytest, API keys, network access, or brokerage connectivity.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tradingagents.agents.utils.rating import parse_rating
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.hard_risk import validate_portfolio_recommendation
from tradingagents.report_artifacts import (
    dashboard_summary_from_artifact,
    load_decision_artifact,
    write_decision_artifact,
)


def recommendation(**updates):
    value = {
        "rating": "Buy",
        "executive_summary": "Enter in stages.",
        "investment_thesis": "Evidence supports the upside case.",
        "proposed_position": 0.06,
        "price_target": 120.0,
        "stop_loss": 90.0,
        "position_sizing": "6% of portfolio",
    }
    value.update(updates)
    return value


def proposal(**updates):
    value = {
        "action": "Buy",
        "conviction": 0.8,
        "reasoning": "Research and market evidence align.",
        "entry_price": 100.0,
        "stop_loss": 90.0,
        "price_target": 120.0,
        "proposed_position": 0.06,
        "position_sizing": "6% of portfolio",
    }
    value.update(updates)
    return value


def context(**updates):
    value = {
        "source": "demo",
        "cash": 100000.0,
        "total_portfolio_value": 100000.0,
        "max_single_position": 0.10,
        "risk_budget": 0.01,
        "current_price": 100.0,
    }
    value.update(updates)
    return value


def main() -> None:
    passed = []

    valid, final = validate_portfolio_recommendation(
        recommendation(), proposal(), context()
    )
    assert valid.status.value == "VALID"
    assert abs(valid.risk_reward_ratio - 2.0) < 1e-9
    assert abs(valid.potential_loss - 600.0) < 1e-9
    assert final.execution_enabled is False
    passed.extend(["valid_buy", "risk_reward", "potential_loss", "execution_disabled"])

    adjusted, adjusted_final = validate_portfolio_recommendation(
        recommendation(proposed_position=0.20),
        proposal(proposed_position=0.20),
        context(),
    )
    assert adjusted.status.value == "ADJUSTED"
    assert abs(adjusted_final.approved_position - 0.10) < 1e-9
    passed.append("single_position_clamp")

    budgeted, budgeted_final = validate_portfolio_recommendation(
        recommendation(proposed_position=0.10),
        proposal(proposed_position=0.10),
        context(risk_budget=0.005),
    )
    assert budgeted.status.value == "ADJUSTED"
    assert abs(budgeted_final.approved_position - 0.05) < 1e-9
    passed.append("risk_budget_clamp")

    cash_limited, cash_final = validate_portfolio_recommendation(
        recommendation(proposed_position=0.10),
        proposal(proposed_position=0.10),
        context(cash=2000.0, ticker_current_position=1000.0),
    )
    assert cash_limited.status.value == "ADJUSTED"
    assert abs(cash_final.approved_position - 0.03) < 1e-9
    passed.append("cash_constraint")

    invalid_stop, _ = validate_portfolio_recommendation(
        recommendation(stop_loss=100), proposal(stop_loss=100), context()
    )
    invalid_target, _ = validate_portfolio_recommendation(
        recommendation(price_target=99), proposal(price_target=99), context()
    )
    assert invalid_stop.status.value == "REJECTED"
    assert invalid_target.status.value == "REJECTED"
    passed.extend(["invalid_stop_rejected", "invalid_target_rejected"])

    missing, missing_final = validate_portfolio_recommendation(
        recommendation(), proposal(), {"source": "unavailable"}
    )
    assert missing.status.value == "INSUFFICIENT_DATA"
    assert missing_final.action.value == "Abstain"
    passed.append("missing_data_abstains")

    no_short, no_short_final = validate_portfolio_recommendation(
        recommendation(rating="Sell"), proposal(action="Sell"),
        context(ticker_current_position=0.0, ticker_current_weight=0.0),
    )
    assert no_short.status.value == "ADJUSTED"
    assert no_short_final.action.value == "Hold"
    passed.append("no_position_no_short_sale")

    logic = ConditionalLogic(max_risk_discuss_rounds=2)
    assert logic.should_continue_risk_analysis({
        "risk_debate_state": {"count": 6, "latest_speaker": "Neutral"}
    }) == "Portfolio Manager"
    passed.append("risk_debate_hard_stop")

    assert parse_rating("**Rating**: Abstain") == "Abstain"
    passed.append("abstain_memory_rating")

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "decision.json"
        write_decision_artifact(
            path,
            ticker="NVDA",
            trade_date="2026-08-12",
            decision_payload=final.model_dump(mode="json"),
            trading_proposal_payload=proposal(),
            risk_reviews_payload=[],
            portfolio_context_payload=context(),
            portfolio_recommendation_payload=recommendation(),
            risk_validation_payload=valid.model_dump(mode="json"),
            evidence_records=[{"tool": "get_stock_data", "status": "SUCCESS"}],
        )
        artifact = load_decision_artifact(path)
        summary = dashboard_summary_from_artifact(artifact)
        assert artifact["llm_recommendation"]["rating"] == "Buy"
        assert artifact["risk_validation"]["status"] == "VALID"
        assert artifact["execution_enabled"] is False
        assert summary["rating"] == "Buy" and summary["price"] == 120.0
        assert summary["risk_validation"] == "VALID"
        assert artifact["evidence_records"][0]["tool"] == "get_stock_data"
        json.loads(path.read_text(encoding="utf-8"))
    passed.extend(["json_round_trip", "typed_dashboard_summary", "evidence_persisted"])

    print(f"Second-round smoke checks passed: {len(passed)}")
    print(", ".join(passed))


if __name__ == "__main__":
    main()
