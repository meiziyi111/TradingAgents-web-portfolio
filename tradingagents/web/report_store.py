"""Read and write dashboard reports without importing the Streamlit app."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.report_artifacts import (
    dashboard_summary_from_artifact,
    load_decision_artifact,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "reports"

SECTION_MAPPING = {
    "市场分析": "market_report",
    "情绪分析": "sentiment_report",
    "新闻分析": "news_report",
    "基本面分析": "fundamentals_report",
    "研究团队决策": "investment_plan",
    "交易团队计划": "trader_investment_plan",
    "最终交易决策": "final_trade_decision",
    "最终交易建议": "final_trade_decision",
    "最终交易提案": "final_trade_decision",
    "风险评估": "risk_assessment",
    "证据链与数据来源": "evidence_chain",
}


def parse_sections(markdown: str) -> dict[str, str]:
    """Split the persisted report by its level-two business headings."""
    sections: dict[str, str] = {}
    current_key: str | None = None
    content: list[str] = []
    for line in markdown.splitlines():
        matched_key = None
        if line.strip().startswith("## "):
            for heading, key in SECTION_MAPPING.items():
                if heading in line:
                    matched_key = key
                    break
        if matched_key:
            if current_key is not None:
                sections[current_key] = "\n".join(content).strip()
            current_key = matched_key
            content = []
        elif current_key is not None:
            content.append(line)
    if current_key is not None:
        sections[current_key] = "\n".join(content).strip()
    return sections


def _normalize_signal(value: str | None) -> str:
    if not value:
        return "N/A"
    cleaned = re.sub(r"[*_`（）()]", " ", str(value)).strip()
    aliases = {
        "买入": "BUY",
        "增持": "OVERWEIGHT",
        "加仓": "OVERWEIGHT",
        "持有": "HOLD",
        "观望": "HOLD",
        "卖出": "SELL",
        "清仓": "SELL",
        "减持": "UNDERWEIGHT",
    }
    return aliases.get(cleaned, cleaned.upper().split()[0] if cleaned else "N/A")


def _capture(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def legacy_summary(sections: Mapping[str, str]) -> dict[str, Any]:
    """Best-effort compatibility for reports created before decision.json."""
    final = sections.get("final_trade_decision", "")
    trader = sections.get("trader_investment_plan", "")
    rating = _normalize_signal(
        _capture(
            final,
            [
                r"Rating\s*[：:]\s*\*{0,2}([A-Za-z]+)",
                r"Recommendation\s*[：:]\s*\*{0,2}([A-Za-z]+)",
                r"评级\s*[：:]?\s*[【\[]?([A-Za-z]+|买入|增持|持有|观望|减持|卖出)",
            ],
        )
    )
    action = _normalize_signal(
        _capture(
            trader,
            [
                r"Action\s*[：:]\s*\*{0,2}(Buy|Hold|Sell|买入|持有|卖出)",
                r"FINAL TRANSACTION PROPOSAL\s*[：:]\s*\*{0,2}(BUY|HOLD|SELL)",
            ],
        )
    )
    price = _capture(
        final + "\n" + trader,
        [r"Price Target\s*[：:]\s*\$?([0-9]+(?:\.[0-9]+)?)", r"目标价(?:位|格)?\s*[：:]\s*\$?([0-9]+(?:\.[0-9]+)?)"],
    )
    stop = _capture(
        final + "\n" + trader,
        [r"Stop Loss\s*[：:]\s*\$?([0-9]+(?:\.[0-9]+)?)", r"止损(?:位|线)?\s*[：:]\s*\$?([0-9]+(?:\.[0-9]+)?)"],
    )
    return {
        "signal": rating if rating != "N/A" else action,
        "rating": rating if rating != "N/A" else action,
        "action": action,
        "price": price or "N/A",
        "stop": stop or "N/A",
        "position_sizing": "N/A",
        "risk_validation": "N/A",
    }


def _validated_report_path(ticker: str, trade_date: str) -> Path:
    normalized_ticker = safe_ticker_component(str(ticker).strip().upper())
    if not normalized_ticker or normalized_ticker != str(ticker).strip().upper():
        raise ValueError("Invalid ticker")
    date.fromisoformat(str(trade_date))
    target = (REPORTS_DIR / normalized_ticker / str(trade_date)).resolve()
    if REPORTS_DIR.resolve() not in target.parents:
        raise ValueError("Invalid report path")
    return target


def list_reports() -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    if not REPORTS_DIR.exists():
        return reports
    for ticker_dir in REPORTS_DIR.iterdir():
        if not ticker_dir.is_dir():
            continue
        for date_dir in ticker_dir.iterdir():
            report_file = date_dir / "complete_report.md"
            if not report_file.exists():
                continue
            modified = datetime.fromtimestamp(
                report_file.stat().st_mtime, tz=timezone.utc
            )
            reports.append(
                {
                    "ticker": ticker_dir.name,
                    "trade_date": date_dir.name,
                    "modified_at": modified.isoformat(),
                    "has_artifact": (date_dir / "decision.json").exists(),
                }
            )
    return sorted(reports, key=lambda item: item["modified_at"], reverse=True)


def load_report(ticker: str, trade_date: str) -> dict[str, Any]:
    report_dir = _validated_report_path(ticker, trade_date)
    markdown_path = report_dir / "complete_report.md"
    if not markdown_path.exists():
        raise FileNotFoundError("Report not found")
    markdown = markdown_path.read_text(encoding="utf-8")
    sections = parse_sections(markdown)
    artifact_path = report_dir / "decision.json"
    artifact: dict[str, Any] | None = None
    if artifact_path.exists():
        artifact = load_decision_artifact(artifact_path)
        summary = dashboard_summary_from_artifact(artifact)
    else:
        summary = legacy_summary(sections)
    return {
        "ticker": ticker,
        "trade_date": trade_date,
        "summary": summary,
        "sections": sections,
        "artifact": artifact,
        "download_name": f"{ticker}_{trade_date}_report.md",
    }
