"""Deterministic post-LLM portfolio risk validation.

This module does not call an LLM and does not execute trades.  It turns a
Portfolio Manager recommendation into an auditable advisory decision under
explicit portfolio limits.
"""

from __future__ import annotations

from typing import Any, Mapping

from tradingagents.agents.schemas import (
    FinalDecision,
    HardRiskValidation,
    PortfolioContext,
    PortfolioDecision,
    PortfolioRating,
    RiskAdjustment,
    RiskValidationStatus,
    TraderAction,
    TraderProposal,
    render_final_decision,
)


def _missing(value: Any) -> bool:
    return value is None or value == ""


def validate_portfolio_recommendation(
    recommendation_payload: Mapping[str, Any],
    proposal_payload: Mapping[str, Any],
    context_payload: Mapping[str, Any],
) -> tuple[HardRiskValidation, FinalDecision]:
    """Validate and, where safe, clamp a proposed long-position decision."""
    recommendation = PortfolioDecision.model_validate(dict(recommendation_payload))
    proposal = TraderProposal.model_validate(dict(proposal_payload))
    context = PortfolioContext.model_validate(dict(context_payload))
    action_for_rating = {
        PortfolioRating.BUY: TraderAction.BUY,
        PortfolioRating.OVERWEIGHT: TraderAction.BUY,
        PortfolioRating.HOLD: TraderAction.HOLD,
        PortfolioRating.UNDERWEIGHT: TraderAction.SELL,
        PortfolioRating.SELL: TraderAction.SELL,
        PortfolioRating.ABSTAIN: TraderAction.ABSTAIN,
    }
    final_action = action_for_rating[recommendation.rating]

    position = (
        recommendation.proposed_position
        if recommendation.proposed_position is not None
        else proposal.proposed_position
    )
    stop_loss = recommendation.stop_loss if recommendation.stop_loss is not None else proposal.stop_loss
    price_target = (
        recommendation.price_target
        if recommendation.price_target is not None
        else proposal.price_target
    )
    current_price = context.current_price
    entry_price = proposal.entry_price if proposal.entry_price is not None else current_price

    checks: dict[str, str] = {}
    adjustments: list[RiskAdjustment] = []
    missing_fields = sorted(set(recommendation.missing_fields + proposal.missing_fields))
    risk_reward = None
    potential_loss = None
    potential_loss_fraction = None

    if proposal.action == TraderAction.ABSTAIN or final_action == TraderAction.ABSTAIN:
        reason = proposal.abstain_reason or recommendation.abstain_reason or "LLM recommendation abstained"
        validation = HardRiskValidation(
            status=RiskValidationStatus.INSUFFICIENT_DATA,
            missing_fields=missing_fields,
            abstain_reason=reason,
        )
        final = FinalDecision(
            action=TraderAction.ABSTAIN,
            rating=PortfolioRating.ABSTAIN,
            validation_status=validation.status,
            rationale=recommendation.executive_summary,
            missing_fields=missing_fields,
            abstain_reason=reason,
        )
        return validation, final

    # HOLD and SELL mean no new long exposure in this project.  SELL is an
    # exit/reduction instruction, not permission to open a short position.
    checks["trader_pm_alignment"] = (
        "PASS" if proposal.action == final_action else
        f"PM_OVERRIDE: Trader proposed {proposal.action.value}; PM implies {final_action.value}"
    )

    if final_action == TraderAction.SELL:
        current_position = context.ticker_current_position
        current_weight = context.ticker_current_weight
        if current_position is None and current_weight is None:
            reason = "Current ticker position is unavailable; cannot validate a reduction without risking a short sale"
            validation = HardRiskValidation(
                status=RiskValidationStatus.INSUFFICIENT_DATA,
                checks=checks,
                missing_fields=["ticker_current_position"],
                abstain_reason=reason,
            )
            final = FinalDecision(
                action=TraderAction.ABSTAIN,
                rating=PortfolioRating.ABSTAIN,
                validation_status=validation.status,
                rationale=recommendation.executive_summary,
                missing_fields=validation.missing_fields,
                abstain_reason=reason,
            )
            return validation, final
        if (current_position or 0.0) <= 0.0 and (current_weight or 0.0) <= 0.0:
            checks["short_sale_guard"] = "NO_POSITION: converted Sell to Hold/avoid-entry"
            validation = HardRiskValidation(
                status=RiskValidationStatus.ADJUSTED,
                checks=checks,
                adjustments=[RiskAdjustment(
                    field="action",
                    original_value="Sell",
                    adjusted_value="Hold",
                    reason="No existing long position; short selling is outside project scope",
                )],
                validated_position=0.0,
            )
            final = FinalDecision(
                action=TraderAction.HOLD,
                rating=recommendation.rating,
                validation_status=validation.status,
                approved_position=0.0,
                rationale=recommendation.executive_summary,
                abstain_reason="Avoid entry; no long position exists to reduce",
            )
            return validation, final

    if final_action in (TraderAction.HOLD, TraderAction.SELL):
        checks["new_long_exposure"] = "NOT_APPLICABLE"
        validation = HardRiskValidation(status=RiskValidationStatus.VALID, checks=checks)
        final = FinalDecision(
            action=final_action,
            rating=recommendation.rating,
            validation_status=validation.status,
            approved_position=position,
            entry_price=entry_price,
            price_target=price_target,
            stop_loss=stop_loss,
            time_horizon=recommendation.time_horizon or proposal.time_horizon,
            rationale=recommendation.executive_summary,
        )
        return validation, final

    required = {
        "current_price": current_price,
        "stop_loss": stop_loss,
        "price_target": price_target,
        "proposed_position": position,
        "max_single_position": context.max_single_position,
        "total_portfolio_value": context.total_portfolio_value,
        "risk_budget": context.risk_budget,
    }
    missing_fields.extend(name for name, value in required.items() if _missing(value))
    missing_fields = sorted(set(missing_fields))
    if missing_fields:
        reason = "Hard risk validation requires missing portfolio or market inputs"
        validation = HardRiskValidation(
            status=RiskValidationStatus.INSUFFICIENT_DATA,
            missing_fields=missing_fields,
            abstain_reason=reason,
        )
        final = FinalDecision(
            action=TraderAction.ABSTAIN,
            rating=PortfolioRating.ABSTAIN,
            validation_status=validation.status,
            rationale=recommendation.executive_summary,
            missing_fields=missing_fields,
            abstain_reason=reason,
        )
        return validation, final

    # Values are proven non-null above; local casts keep calculations explicit.
    current_price = float(current_price)
    stop_loss = float(stop_loss)
    price_target = float(price_target)
    position = float(position)
    approved_position = position

    if stop_loss >= current_price:
        checks["stop_loss"] = "FAIL: BUY stop_loss must be below current_price"
    else:
        checks["stop_loss"] = "PASS"
    if price_target <= current_price:
        checks["price_target"] = "FAIL: BUY price_target must be above current_price"
    else:
        checks["price_target"] = "PASS"

    if checks["stop_loss"].startswith("FAIL") or checks["price_target"].startswith("FAIL"):
        validation = HardRiskValidation(
            status=RiskValidationStatus.REJECTED,
            checks=checks,
            validated_position=0.0,
            abstain_reason="Invalid BUY stop-loss or target relationship",
        )
        final = FinalDecision(
            action=TraderAction.ABSTAIN,
            rating=PortfolioRating.ABSTAIN,
            validation_status=validation.status,
            approved_position=0.0,
            entry_price=entry_price,
            price_target=price_target,
            stop_loss=stop_loss,
            rationale=recommendation.executive_summary,
            abstain_reason=validation.abstain_reason,
        )
        return validation, final

    max_single = float(context.max_single_position)
    if approved_position > max_single:
        adjustments.append(RiskAdjustment(
            field="proposed_position",
            original_value=approved_position,
            adjusted_value=max_single,
            reason="Clamped to max_single_position",
        ))
        approved_position = max_single
        checks["single_position_limit"] = "ADJUSTED"
    else:
        checks["single_position_limit"] = "PASS"

    if context.cash is not None and context.ticker_current_position is not None:
        affordable_weight = (
            float(context.cash) + float(context.ticker_current_position)
        ) / float(context.total_portfolio_value)
        if approved_position > affordable_weight:
            adjustments.append(RiskAdjustment(
                field="proposed_position",
                original_value=approved_position,
                adjusted_value=affordable_weight,
                reason="Clamped to available cash plus existing ticker exposure",
            ))
            approved_position = affordable_weight
            checks["cash_constraint"] = "ADJUSTED"
        else:
            checks["cash_constraint"] = "PASS"
    else:
        checks["cash_constraint"] = "NOT_EVALUATED"

    reward = price_target - current_price
    risk = current_price - stop_loss
    risk_reward = reward / risk
    checks["risk_reward"] = "CALCULATED"

    stop_loss_fraction = risk / current_price
    total_value = float(context.total_portfolio_value)
    risk_budget = float(context.risk_budget)
    potential_loss_fraction = approved_position * stop_loss_fraction
    if potential_loss_fraction > risk_budget:
        risk_budget_position = risk_budget / stop_loss_fraction
        adjustments.append(RiskAdjustment(
            field="proposed_position",
            original_value=approved_position,
            adjusted_value=risk_budget_position,
            reason="Clamped so stop-loss potential loss fits risk_budget",
        ))
        approved_position = risk_budget_position
        potential_loss_fraction = approved_position * stop_loss_fraction
        checks["risk_budget"] = "ADJUSTED"
    else:
        checks["risk_budget"] = "PASS"
    potential_loss = total_value * potential_loss_fraction

    status = RiskValidationStatus.ADJUSTED if adjustments else RiskValidationStatus.VALID
    validation = HardRiskValidation(
        status=status,
        checks=checks,
        adjustments=adjustments,
        risk_reward_ratio=risk_reward,
        potential_loss=potential_loss,
        potential_loss_fraction=potential_loss_fraction,
        validated_position=approved_position,
    )
    final = FinalDecision(
        action=final_action,
        rating=recommendation.rating,
        validation_status=status,
        approved_position=approved_position,
        entry_price=entry_price,
        price_target=price_target,
        stop_loss=stop_loss,
        risk_reward_ratio=risk_reward,
        potential_loss=potential_loss,
        time_horizon=recommendation.time_horizon or proposal.time_horizon,
        rationale=recommendation.executive_summary,
    )
    return validation, final


def hard_risk_node(state) -> dict:
    validation, final = validate_portfolio_recommendation(
        state.get("portfolio_recommendation_structured")
        or state["final_trade_decision_structured"],
        state["trading_proposal_structured"],
        state.get("portfolio_context", {"source": "unavailable"}),
    )
    return {
        "risk_validation": validation.model_dump(mode="json"),
        "final_decision_structured": final.model_dump(mode="json"),
        # Backwards-compatible field now contains the post-validation artifact.
        "final_trade_decision_structured": final.model_dump(mode="json"),
        "final_trade_decision": render_final_decision(final),
    }
