"""Trader: turns the Research Manager's investment plan into a concrete transaction proposal."""

from __future__ import annotations

import functools
import json

from langchain_core.messages import AIMessage

from tradingagents.agents.schemas import TraderProposal, render_trader_proposal
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext_with_artifact,
)


def create_trader(llm):
    structured_llm = bind_structured(llm, TraderProposal, "Trader")

    def trader_node(state, name):
        company_name = state["company_of_interest"]
        asset_type = state.get("asset_type", "stock")
        instrument_context = build_instrument_context(company_name, asset_type)
        investment_plan = state["investment_plan"]
        portfolio_context = state.get("portfolio_context", {})
        reports = {
            "market": state.get("market_report", ""),
            "fundamentals": state.get("fundamentals_report", ""),
            "news": state.get("news_report", ""),
            "sentiment": state.get("sentiment_report", ""),
        }
        past_context = state.get("past_context", "")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a trading agent analyzing market data to make investment decisions. "
                    "Translate the research conclusion into a typed trading proposal. "
                    "Use Abstain and list missing_fields when the supplied evidence is insufficient. "
                    "Never invent current price, portfolio weight, stop loss, or target. "
                    "Return valid JSON matching the required schema."
                    + get_language_instruction()
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Based on a comprehensive analysis by a team of analysts, here is an investment "
                    f"plan tailored for {company_name}. {instrument_context} This plan incorporates "
                    f"research plan.\n\nResearch Manager Plan:\n{investment_plan}\n\n"
                    f"Analyst Reports:\n{json.dumps(reports, ensure_ascii=False)}\n\n"
                    f"Portfolio Context:\n{json.dumps(portfolio_context, ensure_ascii=False)}\n\n"
                    f"Prior Reflections (may be empty):\n{past_context}\n\n"
                    "For proposed_position use a decimal portfolio weight (0.06 means 6%). "
                    "The proposal is advisory and will be checked by deterministic risk rules."
                ),
            },
        ]

        trader_plan, structured_proposal = invoke_structured_or_freetext_with_artifact(
            structured_llm,
            llm,
            messages,
            render_trader_proposal,
            "Trader",
            allow_fallback=False,
        )

        return {
            "messages": [AIMessage(content=trader_plan)],
            "trader_investment_plan": trader_plan,
            "trading_proposal_structured": structured_proposal.model_dump(mode="json"),
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
