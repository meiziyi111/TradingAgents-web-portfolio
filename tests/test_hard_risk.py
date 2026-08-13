"""Deterministic tests for the post-LLM hard risk engine."""

import pytest

from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.hard_risk import validate_portfolio_recommendation


def _recommendation(**updates):
    payload = {
        "rating": "Buy",
        "executive_summary": "Enter in stages.",
        "investment_thesis": "Evidence supports the upside case.",
        "proposed_position": 0.06,
        "price_target": 120.0,
        "stop_loss": 90.0,
        "position_sizing": "6% of portfolio",
    }
    payload.update(updates)
    return payload


def _proposal(**updates):
    payload = {
        "action": "Buy",
        "conviction": 0.8,
        "reasoning": "Research and market evidence align.",
        "entry_price": 100.0,
        "stop_loss": 90.0,
        "price_target": 120.0,
        "proposed_position": 0.06,
        "position_sizing": "6% of portfolio",
    }
    payload.update(updates)
    return payload


def _context(**updates):
    payload = {
        "source": "demo",
        "cash": 100000.0,
        "total_portfolio_value": 100000.0,
        "max_single_position": 0.10,
        "risk_budget": 0.01,
        "current_price": 100.0,
    }
    payload.update(updates)
    return payload


@pytest.mark.unit
def test_valid_buy_passes_and_calculates_risk_reward():
    validation, final = validate_portfolio_recommendation(
        _recommendation(), _proposal(), _context()
    )
    assert validation.status.value == "VALID"
    assert validation.risk_reward_ratio == pytest.approx(2.0)
    assert validation.potential_loss == pytest.approx(600.0)
    assert final.execution_enabled is False


@pytest.mark.unit
def test_single_position_limit_is_clamped_and_audited():
    validation, final = validate_portfolio_recommendation(
        _recommendation(proposed_position=0.20),
        _proposal(proposed_position=0.20),
        _context(),
    )
    assert validation.status.value == "ADJUSTED"
    assert final.approved_position == pytest.approx(0.10)
    assert any(a.field == "proposed_position" for a in validation.adjustments)


@pytest.mark.unit
def test_invalid_buy_stop_is_rejected():
    validation, final = validate_portfolio_recommendation(
        _recommendation(stop_loss=100.0), _proposal(stop_loss=100.0), _context()
    )
    assert validation.status.value == "REJECTED"
    assert final.action.value == "Abstain"


@pytest.mark.unit
def test_invalid_buy_target_is_rejected():
    validation, _ = validate_portfolio_recommendation(
        _recommendation(price_target=99.0), _proposal(price_target=99.0), _context()
    )
    assert validation.status.value == "REJECTED"


@pytest.mark.unit
def test_risk_budget_clamps_position():
    validation, final = validate_portfolio_recommendation(
        _recommendation(proposed_position=0.10),
        _proposal(proposed_position=0.10),
        _context(risk_budget=0.005),
    )
    assert validation.status.value == "ADJUSTED"
    assert final.approved_position == pytest.approx(0.05)


@pytest.mark.unit
def test_missing_context_returns_insufficient_data():
    validation, final = validate_portfolio_recommendation(
        _recommendation(), _proposal(), {"source": "unavailable"}
    )
    assert validation.status.value == "INSUFFICIENT_DATA"
    assert "current_price" in validation.missing_fields
    assert final.action.value == "Abstain"


@pytest.mark.unit
def test_underweight_maps_to_reduce_not_short():
    validation, final = validate_portfolio_recommendation(
        _recommendation(rating="Underweight"), _proposal(action="Hold"),
        _context(ticker_current_position=10000.0, ticker_current_weight=0.10),
    )
    assert validation.status.value == "VALID"
    assert final.action.value == "Sell"


@pytest.mark.unit
def test_sell_without_position_becomes_hold_not_short():
    validation, final = validate_portfolio_recommendation(
        _recommendation(rating="Sell"), _proposal(action="Sell"),
        _context(ticker_current_position=0.0, ticker_current_weight=0.0),
    )
    assert validation.status.value == "ADJUSTED"
    assert final.action.value == "Hold"
    assert validation.checks["short_sale_guard"].startswith("NO_POSITION")


@pytest.mark.unit
def test_buy_position_is_clamped_to_available_cash():
    validation, final = validate_portfolio_recommendation(
        _recommendation(proposed_position=0.10),
        _proposal(proposed_position=0.10),
        _context(cash=2000.0, ticker_current_position=1000.0),
    )
    assert validation.status.value == "ADJUSTED"
    assert final.approved_position == pytest.approx(0.03)
    assert validation.checks["cash_constraint"] == "ADJUSTED"


@pytest.mark.unit
def test_risk_debate_hard_stop_is_preserved():
    logic = ConditionalLogic(max_risk_discuss_rounds=2)
    state = {"risk_debate_state": {"count": 6, "latest_speaker": "Neutral"}}
    assert logic.should_continue_risk_analysis(state) == "Portfolio Manager"
