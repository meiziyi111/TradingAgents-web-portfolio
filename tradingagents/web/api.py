"""FastAPI entrypoint for the React TradingAgents experience."""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.web.report_store import REPORTS_DIR, list_reports, load_report
from tradingagents.web.research_service import STAGES, stream_research


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

app = FastAPI(
    title="TradingAgents Web API",
    version="1.0.0",
    description="Streaming research API. Advisory only; no brokerage execution.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class AnalysisRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=15)
    trade_date: date
    current_price: float | None = Field(default=None, gt=0)
    portfolio_value: float = Field(default=100_000, gt=0)
    cash: float = Field(default=100_000, ge=0)
    current_position: float = Field(default=0, ge=0)
    max_position_pct: float = Field(default=10, gt=0, le=100)
    risk_budget_pct: float = Field(default=1, gt=0, le=20)

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if safe_ticker_component(normalized) != normalized:
            raise ValueError("股票代码包含不支持的字符")
        return normalized

    @model_validator(mode="after")
    def validate_portfolio(self) -> "AnalysisRequest":
        if self.cash > self.portfolio_value:
            raise ValueError("现金不能超过组合总资产")
        if self.current_position > self.portfolio_value:
            raise ValueError("当前持仓不能超过组合总资产")
        if self.cash + self.current_position > self.portfolio_value * 1.001:
            raise ValueError("现金与当前持仓合计不能超过组合总资产")
        return self

    def portfolio_context(self) -> dict:
        return {
            "source": "user_input",
            "cash": self.cash,
            "total_portfolio_value": self.portfolio_value,
            "current_positions": (
                {self.ticker: self.current_position}
                if self.current_position > 0
                else {}
            ),
            "ticker_current_position": self.current_position,
            "ticker_current_weight": self.current_position / self.portfolio_value,
            "max_single_position": self.max_position_pct / 100,
            "risk_budget": self.risk_budget_pct / 100,
            "current_price": self.current_price,
            "price_as_of": (
                self.trade_date.isoformat() if self.current_price is not None else None
            ),
            "notes": "User-supplied portfolio inputs from React; not a brokerage account.",
        }


def _ndjson(events: Iterator[dict]) -> Iterator[str]:
    for event in events:
        yield json.dumps(event, ensure_ascii=False, default=str) + "\n"


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "execution_enabled": False,
        "frontend_built": FRONTEND_DIST.exists(),
    }


@app.get("/api/stages")
def stages() -> dict:
    return {"stages": STAGES}


@app.get("/api/reports")
def reports() -> dict:
    return {"reports": list_reports()}


@app.get("/api/reports/{ticker}/{trade_date}")
def report(ticker: str, trade_date: str) -> dict:
    try:
        return load_report(ticker.strip().upper(), trade_date)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/reports/{ticker}/{trade_date}/download")
def download_report(ticker: str, trade_date: str) -> FileResponse:
    try:
        normalized = safe_ticker_component(ticker.strip().upper())
        if normalized != ticker.strip().upper():
            raise ValueError("Invalid ticker")
        date.fromisoformat(trade_date)
        report_path = REPORTS_DIR / normalized / trade_date / "complete_report.md"
        if not report_path.exists():
            raise FileNotFoundError("Report not found")
        return FileResponse(
            report_path,
            media_type="text/markdown",
            filename=f"{normalized}_{trade_date}_report.md",
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/analysis/stream")
def analysis_stream(payload: AnalysisRequest) -> StreamingResponse:
    events = stream_research(
        ticker=payload.ticker,
        trade_date=payload.trade_date.isoformat(),
        portfolio_context=payload.portfolio_context(),
    )
    return StreamingResponse(
        _ndjson(events),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _demo_events() -> Iterator[dict]:
    available = list_reports()
    if not available:
        yield {"type": "analysis_error", "message": "没有可用于演示的历史报告"}
        return
    chosen = available[0]
    saved_report = load_report(chosen["ticker"], chosen["trade_date"])
    yield {
        "type": "run_started",
        "ticker": chosen["ticker"],
        "trade_date": chosen["trade_date"],
        "stages": STAGES,
        "demo": True,
    }
    section_by_stage = {
        "market": "market_report",
        "sentiment": "sentiment_report",
        "news": "news_report",
        "fundamentals": "fundamentals_report",
        "research": "investment_plan",
        "trader": "trader_investment_plan",
        "risk": "risk_assessment",
        "decision": "final_trade_decision",
    }
    for index, stage in enumerate(STAGES, start=1):
        yield {"type": "stage_started", "stage": stage, "demo": True}
        time.sleep(0.32)
        yield {
            "type": "stage_completed",
            "stage_id": stage["id"],
            "content": saved_report["sections"].get(
                section_by_stage[stage["id"]], "该历史报告没有这一部分。"
            ),
            "completed_count": index,
            "total_count": len(STAGES),
            "demo": True,
        }
    yield {
        "type": "analysis_completed",
        "run_id": "demo-history-replay",
        "report": saved_report,
        "demo": True,
    }


@app.post("/api/analysis/demo-stream")
def demo_stream() -> StreamingResponse:
    return StreamingResponse(
        _ndjson(_demo_events()),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# In a production-style local run, FastAPI serves the Vite build as one app.
# API routes are registered first so the SPA fallback cannot shadow them.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
