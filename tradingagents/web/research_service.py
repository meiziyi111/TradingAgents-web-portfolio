"""Stream real TradingAgents progress as frontend-friendly domain events."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from tradingagents.dataflows.provenance import get_tool_trace, reset_tool_trace
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.llm_clients.api_key_env import get_api_key_env
from tradingagents.report_artifacts import write_decision_artifact
from tradingagents.web.report_store import REPORTS_DIR, load_report


logger = logging.getLogger(__name__)

STAGES = [
    {"id": "market", "label": "市场结构", "role": "Market Analyst", "index": 1},
    {"id": "sentiment", "label": "市场情绪", "role": "Sentiment Analyst", "index": 2},
    {"id": "news", "label": "新闻事件", "role": "News Analyst", "index": 3},
    {"id": "fundamentals", "label": "基本面", "role": "Fundamentals Analyst", "index": 4},
    {"id": "research", "label": "多空辩论", "role": "Research Team", "index": 5},
    {"id": "trader", "label": "交易提案", "role": "Trader", "index": 6},
    {"id": "risk", "label": "风险委员会", "role": "Risk Analysts", "index": 7},
    {"id": "decision", "label": "最终决策", "role": "Portfolio Manager + Hard Risk", "index": 8},
]

TEXT_STAGE_TRIGGERS = {
    "market_report": "market",
    "sentiment_report": "sentiment",
    "news_report": "news",
    "fundamentals_report": "fundamentals",
    "investment_plan": "research",
    "trader_investment_plan": "trader",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(event_type: str, **payload: Any) -> dict[str, Any]:
    return {"type": event_type, "emitted_at": _now(), **payload}


def _risk_markdown(risk_state: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for title, key in [
        ("Aggressive Risk Analyst", "aggressive_history"),
        ("Neutral Risk Analyst", "neutral_history"),
        ("Conservative Risk Analyst", "conservative_history"),
    ]:
        value = risk_state.get(key)
        if value:
            parts.append(f"### {title}\n\n{value}")
    if risk_state.get("judge_decision"):
        parts.append(
            "### Risk Committee Decision\n\n" + str(risk_state["judge_decision"])
        )
    return "\n\n".join(parts)


def _persist_result(
    *,
    ticker: str,
    trade_date: str,
    final_state: Mapping[str, Any],
    graph: TradingAgentsGraph,
    evidence_records: list[dict[str, Any]],
) -> None:
    final_decision = final_state.get("final_decision_structured")
    if not isinstance(final_decision, dict):
        raise RuntimeError("Hard Risk Engine did not return a typed final decision")

    report_dir = REPORTS_DIR / ticker / trade_date
    report_dir.mkdir(parents=True, exist_ok=True)
    write_decision_artifact(
        report_dir / "decision.json",
        ticker=ticker,
        trade_date=trade_date,
        decision_payload=final_decision,
        trading_proposal_payload=final_state.get("trading_proposal_structured"),
        risk_reviews_payload=(final_state.get("risk_debate_state") or {}).get(
            "structured_reviews", []
        ),
        portfolio_context_payload=final_state.get("portfolio_context"),
        portfolio_recommendation_payload=final_state.get(
            "portfolio_recommendation_structured"
        ),
        risk_validation_payload=final_state.get("risk_validation"),
        evidence_records=evidence_records,
        run_id=final_state.get("run_id") or graph.current_run_id,
        trace_summary=(graph.last_trace or {}).get("summary"),
        trace_file=(Path(graph.last_trace_path).name if graph.last_trace_path else None),
    )

    report_path = report_dir / "complete_report.md"
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(f"# {ticker} 完整分析报告\n")
        handle.write(f"分析日期: {trade_date}\n\n")
        for key, title in [
            ("market_report", "## 市场分析报告"),
            ("sentiment_report", "## 情绪分析报告"),
            ("news_report", "## 新闻分析报告"),
            ("fundamentals_report", "## 基本面分析报告"),
            ("investment_plan", "## 研究团队决策"),
            ("trader_investment_plan", "## 交易团队计划"),
            ("final_trade_decision", "## 最终交易决策"),
        ]:
            value = final_state.get(key)
            if value:
                handle.write(f"\n{title}\n\n{value}\n\n---\n")

        risk_markdown = _risk_markdown(final_state.get("risk_debate_state") or {})
        if risk_markdown:
            handle.write(f"\n## 风险评估\n\n{risk_markdown}\n\n---\n")
        handle.write("\n## 证据链与数据来源\n\n")
        if evidence_records:
            for record in evidence_records:
                handle.write(
                    f"- `{record.get('tool')}` via `{record.get('vendor')}` | "
                    f"status={record.get('status')} | source={record.get('source_uri')} | "
                    f"fetched_at={record.get('completed_at') or record.get('requested_at') or 'n/a'} | "
                    f"output_sha256={record.get('output_sha256', 'n/a')}\n"
                )
        else:
            handle.write("- 本次运行未捕获到工具证据记录。\n")
        handle.write(
            "\n说明：报告保存调用元数据与响应哈希，不保存API密钥或模型隐藏推理。"
            "该证据不能替代数据供应商的历史point-in-time保证。\n"
        )


def stream_research(
    *,
    ticker: str,
    trade_date: str,
    portfolio_context: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    """Yield run/stage/result events while the real LangGraph workflow executes."""
    normalized_ticker = ticker.strip().upper()
    started: set[str] = set()
    completed: set[str] = set()
    final_state: dict[str, Any] = {}
    graph: TradingAgentsGraph | None = None

    def start_event(stage_id: str) -> dict[str, Any] | None:
        if stage_id in started or stage_id in completed:
            return None
        started.add(stage_id)
        definition = next(stage for stage in STAGES if stage["id"] == stage_id)
        return _event("stage_started", stage=definition)

    try:
        provider = os.getenv("TRADINGAGENTS_LLM_PROVIDER", "openai").strip().lower()
        key_env = get_api_key_env(provider)
        if key_env and not os.getenv(key_env, "").strip():
            raise RuntimeError(
                f"当前模型提供商为 {provider}，但未配置 {key_env}。"
            )

        config = DEFAULT_CONFIG.copy()
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        config["output_language"] = "Chinese"
        config["checkpoint_enabled"] = True

        reset_tool_trace()
        graph = TradingAgentsGraph(
            selected_analysts=["market", "social", "news", "fundamentals"],
            debug=False,
            config=config,
        )
        yield _event(
            "run_started",
            ticker=normalized_ticker,
            trade_date=trade_date,
            stages=STAGES,
        )
        for analyst_stage in ("market", "sentiment", "news", "fundamentals"):
            event = start_event(analyst_stage)
            if event:
                yield event

        for chunk in graph.stream_propagate(
            normalized_ticker,
            trade_date,
            portfolio_context=portfolio_context,
        ):
            final_state.update(chunk)

            for output_key, stage_id in TEXT_STAGE_TRIGGERS.items():
                value = chunk.get(output_key)
                if value and stage_id not in completed:
                    event = start_event(stage_id)
                    if event:
                        yield event
                    completed.add(stage_id)
                    yield _event(
                        "stage_completed",
                        stage_id=stage_id,
                        content=str(value),
                        completed_count=len(completed),
                        total_count=len(STAGES),
                    )

            if all(
                stage in completed
                for stage in ("market", "sentiment", "news", "fundamentals")
            ):
                event = start_event("research")
                if event:
                    yield event
            if "research" in completed:
                event = start_event("trader")
                if event:
                    yield event
            if "trader" in completed:
                event = start_event("risk")
                if event:
                    yield event

            risk_state = final_state.get("risk_debate_state") or {}
            if (
                isinstance(risk_state, Mapping)
                and risk_state.get("judge_decision")
                and "risk" not in completed
            ):
                completed.add("risk")
                yield _event(
                    "stage_completed",
                    stage_id="risk",
                    content=_risk_markdown(risk_state),
                    completed_count=len(completed),
                    total_count=len(STAGES),
                )
                event = start_event("decision")
                if event:
                    yield event

            final_decision = chunk.get("final_decision_structured")
            if final_decision and "decision" not in completed:
                event = start_event("decision")
                if event:
                    yield event
                completed.add("decision")
                yield _event(
                    "stage_completed",
                    stage_id="decision",
                    content=str(final_state.get("final_trade_decision") or ""),
                    structured=final_decision,
                    completed_count=len(completed),
                    total_count=len(STAGES),
                )

        evidence_records = get_tool_trace()
        _persist_result(
            ticker=normalized_ticker,
            trade_date=trade_date,
            final_state=final_state,
            graph=graph,
            evidence_records=evidence_records,
        )
        report = load_report(normalized_ticker, trade_date)
        yield _event(
            "analysis_completed",
            run_id=final_state.get("run_id") or graph.current_run_id,
            report=report,
        )
    except Exception as exc:
        logger.exception("React API analysis failed for %s on %s", normalized_ticker, trade_date)
        yield _event(
            "analysis_error",
            message=str(exc),
            error_type=type(exc).__name__,
        )
