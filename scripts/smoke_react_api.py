"""Offline checks for the React/FastAPI streaming dashboard.

No LLM key, market API, network call, or broker connection is required.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from tradingagents.web.api import AnalysisRequest, app
from tradingagents.web.report_store import list_reports, load_report
from tradingagents.web.research_service import STAGES
from tradingagents.web.research_service import stream_research


checks: list[str] = []
client = TestClient(app)

assert len(STAGES) == 8
assert [stage["id"] for stage in STAGES][-2:] == ["risk", "decision"]
checks.append("eight_stage_contract")

reports = list_reports()
assert reports
saved = load_report(reports[0]["ticker"], reports[0]["trade_date"])
assert saved["sections"]
assert saved["summary"]["signal"]
checks.append("saved_report_contract")

try:
    AnalysisRequest(
        ticker="NVDA",
        trade_date="2026-07-24",
        portfolio_value=100_000,
        cash=90_000,
        current_position=20_000,
    )
except ValidationError:
    pass
else:
    raise AssertionError("Portfolio over-allocation must be rejected")
checks.append("portfolio_validation")

invalid = client.get("/api/reports/..%2F..%2Fsecrets/2026-07-24")
assert invalid.status_code in (404, 422)
checks.append("report_path_validation")

health = client.get("/api/health")
assert health.status_code == 200
assert health.json()["execution_enabled"] is False
checks.append("health_non_executable")

report_response = client.get(
    f"/api/reports/{reports[0]['ticker']}/{reports[0]['trade_date']}"
)
assert report_response.status_code == 200
assert report_response.json()["ticker"] == reports[0]["ticker"]
checks.append("report_api")

demo = client.post("/api/analysis/demo-stream")
assert demo.status_code == 200
events = [json.loads(line) for line in demo.text.splitlines() if line.strip()]
assert events[0]["type"] == "run_started"
assert events[-1]["type"] == "analysis_completed"
completed = [event for event in events if event["type"] == "stage_completed"]
assert len(completed) == len(STAGES)
assert [event["stage_id"] for event in completed] == [
    stage["id"] for stage in STAGES
]
checks.append("progressive_demo_stream")


class FakeGraph:
    current_run_id = "fake-run"
    last_trace = {"summary": {}}
    last_trace_path = None

    def __init__(self, *args, **kwargs):
        pass

    def stream_propagate(self, *args, **kwargs):
        yield {"market_report": "market"}
        yield {"sentiment_report": "sentiment"}
        yield {"news_report": "news"}
        yield {"fundamentals_report": "fundamentals"}
        yield {"investment_plan": "research"}
        yield {"trader_investment_plan": "trader"}
        yield {"risk_debate_state": {"judge_decision": "risk"}}
        yield {
            "final_trade_decision": "decision",
            "final_decision_structured": {"rating": "Hold"},
        }


fake_report = {
    "ticker": "NVDA",
    "trade_date": "2026-07-24",
    "summary": {"signal": "HOLD"},
    "sections": {"final_trade_decision": "decision"},
}
with (
    patch("tradingagents.web.research_service.TradingAgentsGraph", FakeGraph),
    patch("tradingagents.web.research_service.get_api_key_env", return_value=None),
    patch("tradingagents.web.research_service._persist_result"),
    patch("tradingagents.web.research_service.get_tool_trace", return_value=[]),
    patch("tradingagents.web.research_service.load_report", return_value=fake_report),
):
    ordered_events = list(
        stream_research(
            ticker="NVDA",
            trade_date="2026-07-24",
            portfolio_context={"source": "test"},
        )
    )

for stage in STAGES:
    started_at = next(
        index
        for index, event in enumerate(ordered_events)
        if event["type"] == "stage_started" and event["stage"]["id"] == stage["id"]
    )
    completed_at = next(
        index
        for index, event in enumerate(ordered_events)
        if event["type"] == "stage_completed" and event["stage_id"] == stage["id"]
    )
    assert started_at < completed_at
assert ordered_events[-1]["type"] == "analysis_completed"
checks.append("real_stream_event_order")

frontend = client.get("/")
assert frontend.status_code == 200
assert "TradingAgents" in frontend.text
checks.append("react_build_served")

dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
assert (dist / "index.html").exists()
checks.append("production_bundle_exists")

print(f"React/API smoke checks passed: {len(checks)}")
print(", ".join(checks))
