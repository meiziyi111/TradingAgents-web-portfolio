import json

from tradingagents.agents.schemas import RiskReview, render_risk_review
from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.agents.utils.structured import bind_structured, invoke_structured_or_freetext_with_artifact


def create_conservative_debator(llm):
    structured_llm = bind_structured(llm, RiskReview, "Conservative Risk Analyst")

    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]
        trading_proposal = state.get("trading_proposal_structured", {})

        prompt = f"""As the Conservative Risk Analyst, your primary objective is to protect assets, minimize volatility, and ensure steady, reliable growth. You prioritize stability, security, and risk mitigation, carefully assessing potential losses, economic downturns, and market volatility. When evaluating the trader's decision or plan, critically examine high-risk elements, pointing out where the decision may expose the firm to undue risk and where more cautious alternatives could secure long-term gains. Here is the trader's decision:

Typed Trading Proposal (source of truth):
{json.dumps(trading_proposal, ensure_ascii=False)}

Human-readable rendering:
{trader_decision}

Your task is to actively counter the arguments of the Aggressive and Neutral Analysts, highlighting where their views may overlook potential threats or fail to prioritize sustainability. Respond directly to their points, drawing from the following data sources to build a convincing case for a low-risk approach adjustment to the trader's decision:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here is the last response from the aggressive analyst: {current_aggressive_response} Here is the last response from the neutral analyst: {current_neutral_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

Explicitly assess the action, numeric proposed_position, stop_loss, price_target, risk/reward logic, downside, valuation, event, and position risks. Do not invent missing numbers. Return valid JSON matching the RiskReview schema.""" + get_language_instruction()

        review_text, review = invoke_structured_or_freetext_with_artifact(
            structured_llm, llm, prompt, render_risk_review,
            "Conservative Risk Analyst", allow_fallback=False,
        )
        argument = f"Conservative Analyst: {review_text}"
        structured_reviews = list(risk_debate_state.get("structured_reviews", []))
        structured_reviews.append({"reviewer": "Conservative", **review.model_dump(mode="json")})

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": conservative_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
            "structured_reviews": structured_reviews,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
