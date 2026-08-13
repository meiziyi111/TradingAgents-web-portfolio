"""Pydantic schemas used by agents that produce structured output.

The framework's primary artifact is still prose: each agent's natural-language
reasoning is what users read in the saved markdown reports and what the
downstream agents read as context.  Structured output is layered onto the
three decision-making agents (Research Manager, Trader, Portfolio Manager)
so that:

- Their outputs follow consistent section headers across runs and providers
- Each provider's native structured-output mode is used (json_schema for
  OpenAI/xAI, response_schema for Gemini, tool-use for Anthropic)
- Schema field descriptions become the model's output instructions, freeing
  the prompt body to focus on context and the rating-scale guidance
- A render helper turns the parsed Pydantic instance back into the same
  markdown shape the rest of the system already consumes, so display,
  memory log, and saved reports keep working unchanged
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared rating types
# ---------------------------------------------------------------------------


class PortfolioRating(str, Enum):
    """5-tier rating used by the Research Manager and Portfolio Manager."""

    BUY = "Buy"
    OVERWEIGHT = "Overweight"
    HOLD = "Hold"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"
    ABSTAIN = "Abstain"


class TraderAction(str, Enum):
    """3-tier transaction direction used by the Trader.

    The Trader's job is to translate the Research Manager's investment plan
    into a concrete transaction proposal: should the desk execute a Buy, a
    Sell, or sit on Hold this round.  Position sizing and the nuanced
    Overweight / Underweight calls happen later at the Portfolio Manager.
    """

    BUY = "Buy"
    HOLD = "Hold"
    SELL = "Sell"
    ABSTAIN = "Abstain"


class PortfolioContextSource(str, Enum):
    """Provenance of portfolio inputs used by the risk engine."""

    REAL = "real"
    DEMO = "demo"
    UNAVAILABLE = "unavailable"


class RiskValidationStatus(str, Enum):
    VALID = "VALID"
    ADJUSTED = "ADJUSTED"
    REJECTED = "REJECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Research Manager
# ---------------------------------------------------------------------------


class ResearchPlan(BaseModel):
    """Structured investment plan produced by the Research Manager.

    Hand-off to the Trader: the recommendation pins the directional view,
    the rationale captures which side of the bull/bear debate carried the
    argument, and the strategic actions translate that into concrete
    instructions the trader can execute against.
    """

    recommendation: PortfolioRating = Field(
        description=(
            "The investment recommendation. Exactly one of Buy / Overweight / "
            "Hold / Underweight / Sell. Reserve Hold for situations where the "
            "evidence on both sides is genuinely balanced; otherwise commit to "
            "the side with the stronger arguments."
        ),
    )
    rationale: str = Field(
        description=(
            "Conversational summary of the key points from both sides of the "
            "debate, ending with which arguments led to the recommendation. "
            "Speak naturally, as if to a teammate."
        ),
    )
    strategic_actions: str = Field(
        description=(
            "Concrete steps for the trader to implement the recommendation, "
            "including position sizing guidance consistent with the rating."
        ),
    )


def render_research_plan(plan: ResearchPlan) -> str:
    """Render a ResearchPlan to markdown for storage and the trader's prompt context."""
    return "\n".join([
        f"**Recommendation**: {plan.recommendation.value}",
        "",
        f"**Rationale**: {plan.rationale}",
        "",
        f"**Strategic Actions**: {plan.strategic_actions}",
    ])


# ---------------------------------------------------------------------------
# Trader
# ---------------------------------------------------------------------------


class TraderProposal(BaseModel):
    """Structured transaction proposal produced by the Trader.

    The trader reads the Research Manager's investment plan and the analyst
    reports, then turns them into a concrete transaction: what action to
    take, the reasoning that justifies it, and the practical levels for
    entry, stop-loss, and sizing.
    """

    action: TraderAction = Field(
        description="The transaction direction. Exactly one of Buy / Hold / Sell / Abstain.",
    )
    conviction: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in the proposal from 0.0 to 1.0; not a calibrated probability.",
    )
    reasoning: str = Field(
        description=(
            "The case for this action, anchored in the analysts' reports and "
            "the research plan. Two to four sentences."
        ),
    )
    entry_price: Optional[float] = Field(
        default=None,
        description="Entry price target in the instrument's quote currency. Provide a specific price level.",
    )
    stop_loss: Optional[float] = Field(
        default=None,
        description=(
            "Proposed stop-loss price. Use null instead of guessing when the data "
            "does not support a defensible level."
        ),
    )
    price_target: Optional[float] = Field(
        default=None,
        description="Proposed price target; null when evidence is insufficient.",
    )
    proposed_position: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Proposed post-trade portfolio weight as a decimal, e.g. 0.06 for 6%.",
    )
    position_sizing: Optional[str] = Field(
        default=None,
        description=(
            "Human-readable sizing explanation. The numeric source of truth is "
            "proposed_position."
        ),
    )
    time_horizon: Optional[str] = Field(default=None, description="Expected holding period.")
    key_risks: list[str] = Field(
        default_factory=list,
        description="Specific risks that could invalidate the proposal.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Required inputs that were unavailable; never invent them.",
    )
    abstain_reason: Optional[str] = Field(
        default=None,
        description="Why the Trader abstained, when action is Abstain.",
    )


def render_trader_proposal(proposal: TraderProposal) -> str:
    """Render a TraderProposal to markdown.

    The trailing ``FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`` line is
    preserved for backward compatibility with the analyst stop-signal text
    and any external code that greps for it.
    """
    parts = [
        f"**Action**: {proposal.action.value}",
        "",
        f"**Conviction**: {proposal.conviction:.2f}",
        "",
        f"**Reasoning**: {proposal.reasoning}",
    ]
    if proposal.entry_price is not None:
        parts.extend(["", f"**Entry Price**: {proposal.entry_price}"])
    if proposal.stop_loss is not None:
        parts.extend(["", f"**Stop Loss**: {proposal.stop_loss}"])
    if proposal.price_target is not None:
        parts.extend(["", f"**Price Target**: {proposal.price_target}"])
    if proposal.proposed_position is not None:
        parts.extend(["", f"**Proposed Position**: {proposal.proposed_position:.2%}"])
    if proposal.position_sizing:
        parts.extend(["", f"**Position Sizing**: {proposal.position_sizing}"])
    if proposal.time_horizon:
        parts.extend(["", f"**Time Horizon**: {proposal.time_horizon}"])
    if proposal.key_risks:
        parts.extend(["", "**Key Risks**: " + "; ".join(proposal.key_risks)])
    if proposal.missing_fields:
        parts.extend(["", "**Missing Fields**: " + ", ".join(proposal.missing_fields)])
    if proposal.abstain_reason:
        parts.extend(["", f"**Abstain Reason**: {proposal.abstain_reason}"])
    parts.extend([
        "",
        f"FINAL TRANSACTION PROPOSAL: **{proposal.action.value.upper()}**",
    ])
    return "\n".join(parts)


# Public business name; retain TraderProposal for backwards compatibility.
TradingProposal = TraderProposal


class RiskReview(BaseModel):
    """Typed review of the Trader proposal by one risk perspective."""

    accept_action: bool = Field(description="Whether this reviewer accepts the proposed action.")
    position_assessment: str
    stop_loss_assessment: str
    price_target_assessment: str
    risk_reward_assessment: str
    key_risks: list[str] = Field(default_factory=list)
    adjustment_recommendations: list[str] = Field(default_factory=list)
    narrative: str = Field(description="Concise debate argument grounded in the supplied evidence.")


def render_risk_review(review: RiskReview) -> str:
    return "\n".join([
        f"**Accept Action**: {'Yes' if review.accept_action else 'No'}",
        f"**Position Assessment**: {review.position_assessment}",
        f"**Stop Loss Assessment**: {review.stop_loss_assessment}",
        f"**Price Target Assessment**: {review.price_target_assessment}",
        f"**Risk/Reward Assessment**: {review.risk_reward_assessment}",
        "**Key Risks**: " + ("; ".join(review.key_risks) or "None identified"),
        "**Adjustments**: " + ("; ".join(review.adjustment_recommendations) or "None"),
        f"**Narrative**: {review.narrative}",
    ])


class PortfolioContext(BaseModel):
    """Portfolio facts and policy limits, with explicit provenance."""

    source: PortfolioContextSource = PortfolioContextSource.UNAVAILABLE
    cash: Optional[float] = Field(default=None, ge=0.0)
    total_portfolio_value: Optional[float] = Field(default=None, gt=0.0)
    current_positions: dict[str, float] = Field(default_factory=dict)
    ticker_current_position: Optional[float] = Field(default=None, ge=0.0)
    ticker_current_weight: Optional[float] = Field(default=None, ge=0.0)
    sector_exposure: Optional[float] = Field(default=None, ge=0.0)
    max_single_position: Optional[float] = Field(default=None, gt=0.0, le=1.0)
    max_sector_exposure: Optional[float] = Field(default=None, gt=0.0, le=1.0)
    risk_budget: Optional[float] = Field(default=None, gt=0.0, le=1.0)
    current_price: Optional[float] = Field(default=None, gt=0.0)
    price_as_of: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Portfolio Manager
# ---------------------------------------------------------------------------


class PortfolioDecision(BaseModel):
    """Structured output produced by the Portfolio Manager.

    The model fills every field as part of its primary LLM call; no separate
    extraction pass is required. Field descriptions double as the model's
    output instructions, so the prompt body only needs to convey context and
    the rating-scale guidance.
    """

    rating: PortfolioRating = Field(
        description=(
            "The final position rating. Exactly one of Buy / Overweight / Hold / "
            "Underweight / Sell / Abstain. Use Abstain when evidence is insufficient."
        ),
    )
    executive_summary: str = Field(
        description=(
            "A concise action plan covering entry strategy, position sizing, "
            "key risk levels, and time horizon. Two to four sentences."
        ),
    )
    investment_thesis: str = Field(
        description=(
            "Detailed reasoning anchored in specific evidence from the analysts' "
            "debate. If prior lessons are referenced in the prompt context, "
            "incorporate them; otherwise rely solely on the current analysis."
        ),
    )
    proposed_position: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Proposed post-trade portfolio weight as a decimal.",
    )
    price_target: Optional[float] = Field(
        default=None,
        description=(
            "REQUIRED: target price in the instrument's quote currency. "
            "Provide a concrete price target based on technical and fundamental analysis."
        ),
    )
    stop_loss: Optional[float] = Field(
        default=None,
        description=(
            "REQUIRED: stop-loss price in the instrument's quote currency. "
            "Provide a concrete stop-loss level based on support levels or risk parameters."
        ),
    )
    position_sizing: Optional[str] = Field(
        default=None,
        description=(
            "REQUIRED: explain the recommended position size or exposure limit, "
            "including a percentage or concrete sizing rule and why it fits the risk."
        ),
    )
    time_horizon: Optional[str] = Field(
        default=None,
        description="Optional recommended holding period, e.g. '3-6 months'.",
    )
    missing_fields: list[str] = Field(default_factory=list)
    abstain_reason: Optional[str] = None


def render_pm_decision(decision: PortfolioDecision) -> str:
    """Render a PortfolioDecision back to the markdown shape the rest of the system expects.

    Memory log, CLI display, and saved report files all read this markdown,
    so the rendered output preserves the exact section headers (``**Rating**``,
    ``**Executive Summary**``, ``**Investment Thesis**``) that downstream
    parsers and the report writers already handle.
    """
    parts = [
        f"**Rating**: {decision.rating.value}",
        "",
        f"**Executive Summary**: {decision.executive_summary}",
        "",
        f"**Investment Thesis**: {decision.investment_thesis}",
    ]
    if decision.proposed_position is not None:
        parts.extend(["", f"**Proposed Position**: {decision.proposed_position:.2%}"])
    if decision.price_target is not None:
        parts.extend(["", f"**Price Target**: {decision.price_target}"])
    if decision.stop_loss is not None:
        parts.extend(["", f"**Stop Loss**: {decision.stop_loss}"])
    if decision.position_sizing:
        parts.extend(["", f"**Position Sizing**: {decision.position_sizing}"])
    if decision.time_horizon:
        parts.extend(["", f"**Time Horizon**: {decision.time_horizon}"])
    if decision.missing_fields:
        parts.extend(["", "**Missing Fields**: " + ", ".join(decision.missing_fields)])
    if decision.abstain_reason:
        parts.extend(["", f"**Abstain Reason**: {decision.abstain_reason}"])
    return "\n".join(parts)


class RiskAdjustment(BaseModel):
    field: str
    original_value: Any = None
    adjusted_value: Any = None
    reason: str


class HardRiskValidation(BaseModel):
    """Deterministic validation result; no field is generated by an LLM."""

    status: RiskValidationStatus
    checks: dict[str, str] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    adjustments: list[RiskAdjustment] = Field(default_factory=list)
    risk_reward_ratio: Optional[float] = None
    potential_loss: Optional[float] = None
    potential_loss_fraction: Optional[float] = None
    validated_position: Optional[float] = None
    abstain_reason: Optional[str] = None


class FinalDecision(BaseModel):
    """Post-risk-engine decision used by storage and the dashboard."""

    action: TraderAction
    rating: PortfolioRating
    validation_status: RiskValidationStatus
    approved_position: Optional[float] = None
    entry_price: Optional[float] = None
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    potential_loss: Optional[float] = None
    time_horizon: Optional[str] = None
    rationale: str
    missing_fields: list[str] = Field(default_factory=list)
    abstain_reason: Optional[str] = None
    execution_enabled: Literal[False] = False


def render_final_decision(decision: FinalDecision) -> str:
    parts = [
        f"**Rating**: {decision.rating.value}",
        "",
        f"**Action**: {decision.action.value}",
        "",
        f"**Risk Validation**: {decision.validation_status.value}",
        "",
        f"**Rationale**: {decision.rationale}",
    ]
    if decision.approved_position is not None:
        parts.extend(["", f"**Approved Position**: {decision.approved_position:.2%}"])
        parts.extend(["", f"**Position Sizing**: {decision.approved_position:.2%} of portfolio"])
    if decision.entry_price is not None:
        parts.extend(["", f"**Entry Price**: {decision.entry_price}"])
    if decision.price_target is not None:
        parts.extend(["", f"**Price Target**: {decision.price_target}"])
    if decision.stop_loss is not None:
        parts.extend(["", f"**Stop Loss**: {decision.stop_loss}"])
    if decision.risk_reward_ratio is not None:
        parts.extend(["", f"**Risk/Reward**: {decision.risk_reward_ratio:.2f}"])
    if decision.potential_loss is not None:
        parts.extend(["", f"**Potential Loss**: {decision.potential_loss:.2f}"])
    if decision.time_horizon:
        parts.extend(["", f"**Time Horizon**: {decision.time_horizon}"])
    if decision.missing_fields:
        parts.extend(["", "**Missing Fields**: " + ", ".join(decision.missing_fields)])
    if decision.abstain_reason:
        parts.extend(["", f"**Abstain Reason**: {decision.abstain_reason}"])
    parts.extend(["", "**Execution Enabled**: false"])
    return "\n".join(parts)
