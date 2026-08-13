"""Per-run, machine-readable tool provenance for research auditability."""

from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping

from tradingagents.observability import current_run_id, record_completed_span


_TOOL_TRACE: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "tradingagents_tool_trace", default=None
)


def reset_tool_trace(run_id: str | None = None) -> None:
    """Reset per-run tool evidence; run_id is accepted for API compatibility."""
    _TOOL_TRACE.set([])


def record_tool_trace(record: Mapping[str, Any]) -> None:
    enriched = dict(record)
    run_id = current_run_id()
    if run_id:
        enriched.setdefault("run_id", run_id)
    duration_ms = _duration_ms(
        enriched.get("requested_at"), enriched.get("completed_at")
    )
    if duration_ms is not None:
        enriched.setdefault("duration_ms", duration_ms)
    span_id = record_completed_span(
        name=str(enriched.get("tool", "unknown_tool")),
        kind="tool",
        status=str(enriched.get("status", "UNKNOWN")),
        started_at=enriched.get("requested_at"),
        ended_at=enriched.get("completed_at"),
        duration_ms=enriched.get("duration_ms"),
        error_type=enriched.get("error_type"),
        error=enriched.get("error"),
        attributes={
            "vendor": enriched.get("vendor"),
            "attempt": enriched.get("attempt"),
            "source_uri": enriched.get("source_uri"),
            "output_sha256": enriched.get("output_sha256"),
        },
    )
    if span_id:
        enriched.setdefault("span_id", span_id)
    trace = list(_TOOL_TRACE.get() or [])
    trace.append(enriched)
    _TOOL_TRACE.set(trace)


def get_tool_trace() -> list[dict[str, Any]]:
    return deepcopy(_TOOL_TRACE.get() or [])


def _duration_ms(started_at: Any, completed_at: Any) -> float | None:
    if not started_at or not completed_at:
        return None
    try:
        start = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
        return round((end - start).total_seconds() * 1000, 3)
    except (TypeError, ValueError):
        return None
