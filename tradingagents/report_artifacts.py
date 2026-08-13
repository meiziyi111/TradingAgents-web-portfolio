"""Typed, durable report artifacts for the portfolio demo.

The graph continues to keep Markdown reports for humans.  This module keeps
the final Portfolio Manager decision as validated JSON as well, so a dashboard
does not need to infer business fields from prose with regular expressions.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from tradingagents.agents.schemas import (
    FinalDecision,
    HardRiskValidation,
    PortfolioContext,
    PortfolioDecision,
    RiskReview,
    TraderProposal,
)


DECISION_ARTIFACT_VERSION = "2.0"
LEGACY_DECISION_ARTIFACT_VERSION = "1.0"


def build_decision_artifact(
    *,
    ticker: str,
    trade_date: str,
    decision_payload: Mapping[str, Any],
    trading_proposal_payload: Optional[Mapping[str, Any]] = None,
    risk_reviews_payload: Optional[Sequence[Mapping[str, Any]]] = None,
    portfolio_context_payload: Optional[Mapping[str, Any]] = None,
    portfolio_recommendation_payload: Optional[Mapping[str, Any]] = None,
    risk_validation_payload: Optional[Mapping[str, Any]] = None,
    evidence_records: Optional[Sequence[Mapping[str, Any]]] = None,
    run_id: Optional[str] = None,
    trace_summary: Optional[Mapping[str, Any]] = None,
    trace_file: Optional[str] = None,
) -> dict[str, Any]:
    """Validate and envelope a PM decision before it crosses the report boundary."""
    is_full_artifact = all([
        trading_proposal_payload is not None,
        portfolio_context_payload is not None,
        portfolio_recommendation_payload is not None,
        risk_validation_payload is not None,
    ])
    if not is_full_artifact:
        # Backwards-compatible helper path retained for old callers/tests.
        decision = PortfolioDecision.model_validate(dict(decision_payload))
        artifact = {
            "schema_version": LEGACY_DECISION_ARTIFACT_VERSION,
            "artifact_type": "portfolio_decision",
            "ticker": ticker,
            "trade_date": trade_date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "execution_enabled": False,
            "decision": decision.model_dump(mode="json"),
        }
        if run_id:
            artifact["run_id"] = run_id
        if trace_summary:
            artifact["trace_summary"] = dict(trace_summary)
        if trace_file:
            artifact["trace_file"] = trace_file
        return artifact

    proposal = TraderProposal.model_validate(dict(trading_proposal_payload))
    context = PortfolioContext.model_validate(dict(portfolio_context_payload))
    recommendation = PortfolioDecision.model_validate(dict(portfolio_recommendation_payload))
    validation = HardRiskValidation.model_validate(dict(risk_validation_payload))
    final_decision = FinalDecision.model_validate(dict(decision_payload))
    reviews = []
    for raw in risk_reviews_payload or []:
        raw_dict = dict(raw)
        reviewer = raw_dict.pop("reviewer", "Unknown")
        review = RiskReview.model_validate(raw_dict)
        reviews.append({"reviewer": reviewer, **review.model_dump(mode="json")})
    artifact = {
        "schema_version": DECISION_ARTIFACT_VERSION,
        "artifact_type": "portfolio_decision",
        "ticker": ticker,
        "trade_date": trade_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # This is an investment-research demonstration, never an execution order.
        "execution_enabled": False,
        "trading_proposal": proposal.model_dump(mode="json"),
        "risk_assessments": reviews,
        "portfolio_context": context.model_dump(mode="json"),
        "llm_recommendation": recommendation.model_dump(mode="json"),
        "risk_validation": validation.model_dump(mode="json"),
        "final_decision": final_decision.model_dump(mode="json"),
        "evidence_records": [dict(record) for record in (evidence_records or [])],
        # Deprecated compatibility alias for consumers of the v1 artifact.
        "decision": final_decision.model_dump(mode="json"),
    }
    if run_id:
        artifact["run_id"] = run_id
    if trace_summary:
        artifact["trace_summary"] = dict(trace_summary)
    if trace_file:
        artifact["trace_file"] = trace_file
    return artifact


def write_decision_artifact(
    path: str | Path,
    *,
    ticker: str,
    trade_date: str,
    decision_payload: Mapping[str, Any],
    trading_proposal_payload: Optional[Mapping[str, Any]] = None,
    risk_reviews_payload: Optional[Sequence[Mapping[str, Any]]] = None,
    portfolio_context_payload: Optional[Mapping[str, Any]] = None,
    portfolio_recommendation_payload: Optional[Mapping[str, Any]] = None,
    risk_validation_payload: Optional[Mapping[str, Any]] = None,
    evidence_records: Optional[Sequence[Mapping[str, Any]]] = None,
    run_id: Optional[str] = None,
    trace_summary: Optional[Mapping[str, Any]] = None,
    trace_file: Optional[str] = None,
) -> dict[str, Any]:
    """Atomically write a validated final-decision artifact and return it."""
    target = Path(path)
    artifact = build_decision_artifact(
        ticker=ticker,
        trade_date=trade_date,
        decision_payload=decision_payload,
        trading_proposal_payload=trading_proposal_payload,
        risk_reviews_payload=risk_reviews_payload,
        portfolio_context_payload=portfolio_context_payload,
        portfolio_recommendation_payload=portfolio_recommendation_payload,
        risk_validation_payload=risk_validation_payload,
        evidence_records=evidence_records,
        run_id=run_id,
        trace_summary=trace_summary,
        trace_file=trace_file,
    )
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(artifact, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, target)
    finally:
        # ``os.replace`` has already removed the temporary file on success.
        if temporary.exists():
            temporary.unlink()
    return artifact


def load_decision_artifact(path: str | Path) -> dict[str, Any]:
    """Load and validate a decision artifact, rejecting unknown shapes early."""
    with Path(path).open("r", encoding="utf-8") as handle:
        artifact = json.load(handle)
    version = artifact.get("schema_version")
    if version not in (LEGACY_DECISION_ARTIFACT_VERSION, DECISION_ARTIFACT_VERSION):
        raise ValueError("Unsupported decision artifact schema version")
    if artifact.get("artifact_type") != "portfolio_decision":
        raise ValueError("Unexpected report artifact type")
    if version == LEGACY_DECISION_ARTIFACT_VERSION:
        decision = PortfolioDecision.model_validate(artifact.get("decision"))
        artifact["decision"] = decision.model_dump(mode="json")
        return artifact

    proposal = TraderProposal.model_validate(artifact.get("trading_proposal"))
    context = PortfolioContext.model_validate(artifact.get("portfolio_context"))
    recommendation = PortfolioDecision.model_validate(artifact.get("llm_recommendation"))
    validation = HardRiskValidation.model_validate(artifact.get("risk_validation"))
    final_decision = FinalDecision.model_validate(artifact.get("final_decision"))
    validated_reviews = []
    for raw in artifact.get("risk_assessments", []):
        raw_dict = dict(raw)
        reviewer = raw_dict.pop("reviewer", "Unknown")
        review = RiskReview.model_validate(raw_dict)
        validated_reviews.append({"reviewer": reviewer, **review.model_dump(mode="json")})
    if artifact.get("execution_enabled") is not False or final_decision.execution_enabled is not False:
        raise ValueError("Execution must remain disabled for portfolio artifacts")
    artifact["trading_proposal"] = proposal.model_dump(mode="json")
    artifact["portfolio_context"] = context.model_dump(mode="json")
    artifact["llm_recommendation"] = recommendation.model_dump(mode="json")
    artifact["risk_validation"] = validation.model_dump(mode="json")
    artifact["risk_assessments"] = validated_reviews
    artifact["final_decision"] = final_decision.model_dump(mode="json")
    artifact["evidence_records"] = [
        dict(record) for record in artifact.get("evidence_records", [])
    ]
    artifact["decision"] = artifact["final_decision"]
    return artifact


def dashboard_summary_from_artifact(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Return UI headline fields directly from typed JSON, without regex."""
    decision = artifact.get("final_decision") or artifact.get("decision") or {}
    approved_position = decision.get("approved_position")
    return {
        "signal": decision.get("rating", "N/A"),
        "rating": decision.get("rating", "N/A"),
        "action": decision.get("action"),
        "price": decision.get("price_target") or "N/A",
        "stop": decision.get("stop_loss") or "N/A",
        "position_sizing": (
            f"{approved_position:.2%}" if approved_position is not None
            else decision.get("position_sizing") or "N/A"
        ),
        "risk_validation": decision.get("validation_status", "N/A"),
    }
