"""Tests for the typed report-boundary contract."""

import json

import pytest
from pydantic import ValidationError

from tradingagents.report_artifacts import (
    build_decision_artifact,
    load_decision_artifact,
    write_decision_artifact,
)


def _decision():
    return {
        "rating": "Overweight",
        "executive_summary": "Build gradually.",
        "investment_thesis": "The bull case has stronger evidence.",
        "price_target": 215.0,
        "stop_loss": 178.0,
        "position_sizing": "6% of portfolio",
        "time_horizon": "3-6 months",
    }


@pytest.mark.unit
def test_artifact_is_validated_and_explicitly_non_executable(tmp_path):
    path = tmp_path / "decision.json"
    written = write_decision_artifact(
        path, ticker="NVDA", trade_date="2026-08-12", decision_payload=_decision()
    )
    assert written["execution_enabled"] is False
    assert path.exists()
    assert load_decision_artifact(path)["decision"]["price_target"] == 215.0


@pytest.mark.unit
def test_artifact_rejects_missing_required_risk_field():
    invalid = _decision()
    invalid.pop("stop_loss")
    with pytest.raises(ValidationError):
        build_decision_artifact(
            ticker="NVDA", trade_date="2026-08-12", decision_payload=invalid
        )


@pytest.mark.unit
def test_artifact_write_is_not_partial_when_validation_fails(tmp_path):
    path = tmp_path / "decision.json"
    with pytest.raises(ValidationError):
        write_decision_artifact(
            path,
            ticker="NVDA",
            trade_date="2026-08-12",
            decision_payload={"rating": "Buy"},
        )
    assert not path.exists()
    assert not (tmp_path / "decision.json.tmp").exists()


@pytest.mark.unit
def test_loader_rejects_unknown_artifact_version(tmp_path):
    path = tmp_path / "decision.json"
    path.write_text(json.dumps({"schema_version": "unknown"}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema version"):
        load_decision_artifact(path)


@pytest.mark.unit
def test_v2_artifact_keeps_recommendation_validation_and_final_separate(tmp_path):
    path = tmp_path / "decision.json"
    proposal = {
        "action": "Buy", "reasoning": "evidence", "proposed_position": 0.05,
        "stop_loss": 90.0, "price_target": 120.0,
    }
    context = {
        "source": "demo", "total_portfolio_value": 100000.0,
        "max_single_position": 0.10, "risk_budget": 0.01, "current_price": 100.0,
    }
    recommendation = _decision() | {"proposed_position": 0.05}
    validation = {
        "status": "VALID", "checks": {"stop_loss": "PASS"},
        "risk_reward_ratio": 2.0, "validated_position": 0.05,
    }
    final = {
        "action": "Buy", "rating": "Overweight", "validation_status": "VALID",
        "approved_position": 0.05, "entry_price": 100.0, "price_target": 215.0,
        "stop_loss": 178.0, "risk_reward_ratio": 2.0,
        "rationale": "Build gradually.", "execution_enabled": False,
    }
    write_decision_artifact(
        path, ticker="NVDA", trade_date="2026-08-12", decision_payload=final,
        trading_proposal_payload=proposal, risk_reviews_payload=[],
        portfolio_context_payload=context,
        portfolio_recommendation_payload=recommendation,
        risk_validation_payload=validation,
    )
    loaded = load_decision_artifact(path)
    assert loaded["schema_version"] == "2.0"
    assert loaded["llm_recommendation"]["rating"] == "Overweight"
    assert loaded["risk_validation"]["status"] == "VALID"
    assert loaded["final_decision"]["action"] == "Buy"
    assert loaded["execution_enabled"] is False


@pytest.mark.unit
def test_v2_loader_rejects_execution_enable_tampering(tmp_path):
    path = tmp_path / "decision.json"
    path.write_text(json.dumps({
        "schema_version": "2.0",
        "artifact_type": "portfolio_decision",
        "execution_enabled": True,
        "trading_proposal": {
            "action": "Hold", "reasoning": "wait",
        },
        "risk_assessments": [],
        "portfolio_context": {"source": "demo"},
        "llm_recommendation": {
            "rating": "Hold", "executive_summary": "wait",
            "investment_thesis": "balanced",
        },
        "risk_validation": {"status": "VALID"},
        "final_decision": {
            "action": "Hold", "rating": "Hold", "validation_status": "VALID",
            "rationale": "wait", "execution_enabled": False,
        },
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Execution must remain disabled"):
        load_decision_artifact(path)
