import json

from tradingagents.agents.schemas import RiskReview, render_risk_review
from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.agents.utils.structured import bind_structured, invoke_structured_or_freetext_with_artifact


def create_neutral_debator(llm):
    structured_llm = bind_structured(llm, RiskReview, "Neutral Risk Analyst")

    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]
        trading_proposal = state.get("trading_proposal_structured", {})

        prompt = f"""As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing both the potential benefits and risks of the trader's decision or plan. You prioritize a well-rounded approach, evaluating the upsides and downsides while factoring in broader market trends, potential economic shifts, and diversification strategies.Here is the trader's decision:

Typed Trading Proposal (source of truth):
{json.dumps(trading_proposal, ensure_ascii=False)}

Human-readable rendering:
{trader_decision}

Your task is to challenge both the Aggressive and Conservative Analysts, pointing out where each perspective may be overly optimistic or overly cautious. Use insights from the following data sources to support a moderate, sustainable strategy to adjust the trader's decision:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here is the last response from the aggressive analyst: {current_aggressive_response} Here is the last response from the conservative analyst: {current_conservative_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

Explicitly assess the action, numeric proposed_position, stop_loss, price_target, risk/reward balance, and concrete adjustment options. Do not invent missing numbers. Return valid JSON matching the RiskReview schema.""" + get_language_instruction()

        review_text, review = invoke_structured_or_freetext_with_artifact(
            structured_llm, llm, prompt, render_risk_review,
            "Neutral Risk Analyst", allow_fallback=False,
        )
        argument = f"Neutral Analyst: {review_text}"
        structured_reviews = list(risk_debate_state.get("structured_reviews", []))
        structured_reviews.append({"reviewer": "Neutral", **review.model_dump(mode="json")})

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": argument,
            "count": risk_debate_state["count"] + 1,
            "structured_reviews": structured_reviews,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
