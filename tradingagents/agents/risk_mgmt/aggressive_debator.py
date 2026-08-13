import json

from tradingagents.agents.schemas import RiskReview, render_risk_review
from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.agents.utils.structured import bind_structured, invoke_structured_or_freetext_with_artifact


def create_aggressive_debator(llm):
    structured_llm = bind_structured(llm, RiskReview, "Aggressive Risk Analyst")

    def aggressive_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]
        trading_proposal = state.get("trading_proposal_structured", {})

        prompt = f"""As the Aggressive Risk Analyst, your role is to actively champion high-reward, high-risk opportunities, emphasizing bold strategies and competitive advantages. When evaluating the trader's decision or plan, focus intently on the potential upside, growth potential, and innovative benefits—even when these come with elevated risk. Use the provided market data and sentiment analysis to strengthen your arguments and challenge the opposing views. Specifically, respond directly to each point made by the conservative and neutral analysts, countering with data-driven rebuttals and persuasive reasoning. Highlight where their caution might miss critical opportunities or where their assumptions may be overly conservative. Here is the trader's decision:

Typed Trading Proposal (source of truth):
{json.dumps(trading_proposal, ensure_ascii=False)}

Human-readable rendering:
{trader_decision}

Your task is to create a compelling case for the trader's decision by questioning and critiquing the conservative and neutral stances to demonstrate why your high-reward perspective offers the best path forward. Incorporate insights from the following sources into your arguments:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here are the last arguments from the conservative analyst: {current_conservative_response} Here are the last arguments from the neutral analyst: {current_neutral_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

Explicitly assess the action, numeric proposed_position, stop_loss, price_target, risk/reward logic, and thesis-breaking risks. Do not invent missing numbers. Return valid JSON matching the RiskReview schema.""" + get_language_instruction()

        review_text, review = invoke_structured_or_freetext_with_artifact(
            structured_llm, llm, prompt, render_risk_review,
            "Aggressive Risk Analyst", allow_fallback=False,
        )
        argument = f"Aggressive Analyst: {review_text}"
        structured_reviews = list(risk_debate_state.get("structured_reviews", []))
        structured_reviews.append({"reviewer": "Aggressive", **review.model_dump(mode="json")})

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": aggressive_history + "\n" + argument,
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Aggressive",
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
            "structured_reviews": structured_reviews,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
