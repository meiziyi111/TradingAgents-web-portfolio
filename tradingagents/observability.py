"""Lightweight, dependency-free run/span tracing for the portfolio demo."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Iterator, Mapping, Optional
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceRecorder:
    """Thread-safe mutable recorder shared by copied execution contexts."""

    def __init__(self, run_id: str, attributes: Optional[Mapping[str, Any]] = None):
        self.run_id = run_id
        self.root_span_id = uuid4().hex
        self.started_at = _utc_now()
        self.ended_at: Optional[str] = None
        self.status = "RUNNING"
        self.error: Optional[str] = None
        self.attributes = dict(attributes or {})
        self._lock = threading.Lock()
        self._spans: list[dict[str, Any]] = []
        self._root_started_perf = time.perf_counter()

    def append(self, span: Mapping[str, Any]) -> None:
        with self._lock:
            self._spans.append(dict(span))

    def finish(self, status: str, error: Optional[str] = None) -> None:
        self.ended_at = _utc_now()
        self.status = status
        self.error = error

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            spans = deepcopy(self._spans)
        duration_ms = round((time.perf_counter() - self._root_started_perf) * 1000, 3)
        status_counts: dict[str, int] = {}
        kind_counts: dict[str, int] = {}
        for span in spans:
            status = str(span.get("status", "UNKNOWN"))
            kind = str(span.get("kind", "unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
        return {
            "schema_version": "1.0",
            "run_id": self.run_id,
            "root_span_id": self.root_span_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": duration_ms,
            "status": self.status,
            "error": self.error,
            "attributes": deepcopy(self.attributes),
            "summary": {
                "span_count": len(spans),
                "status_counts": status_counts,
                "kind_counts": kind_counts,
            },
            "spans": spans,
        }


_ACTIVE_TRACE: ContextVar[Optional[TraceRecorder]] = ContextVar(
    "tradingagents_active_trace", default=None
)
_ACTIVE_SPAN_ID: ContextVar[Optional[str]] = ContextVar(
    "tradingagents_active_span_id", default=None
)


def start_trace(
    *,
    run_id: Optional[str] = None,
    attributes: Optional[Mapping[str, Any]] = None,
) -> str:
    recorder = TraceRecorder(run_id or uuid4().hex, attributes)
    _ACTIVE_TRACE.set(recorder)
    _ACTIVE_SPAN_ID.set(recorder.root_span_id)
    return recorder.run_id


def current_run_id() -> Optional[str]:
    recorder = _ACTIVE_TRACE.get()
    return recorder.run_id if recorder else None


def current_span_id() -> Optional[str]:
    return _ACTIVE_SPAN_ID.get()


def finish_trace(status: str, error: Optional[str] = None) -> dict[str, Any]:
    recorder = _ACTIVE_TRACE.get()
    if recorder is None:
        return {}
    recorder.finish(status, error)
    return recorder.snapshot()


def get_trace_snapshot() -> dict[str, Any]:
    recorder = _ACTIVE_TRACE.get()
    return recorder.snapshot() if recorder else {}


@contextmanager
def trace_span(
    name: str,
    kind: str,
    *,
    attributes: Optional[Mapping[str, Any]] = None,
) -> Iterator[Optional[str]]:
    recorder = _ACTIVE_TRACE.get()
    if recorder is None:
        yield None
        return

    span_id = uuid4().hex
    parent_span_id = _ACTIVE_SPAN_ID.get() or recorder.root_span_id
    started_at = _utc_now()
    started_perf = time.perf_counter()
    token = _ACTIVE_SPAN_ID.set(span_id)
    status = "SUCCESS"
    error_type = None
    error = None
    try:
        yield span_id
    except Exception as exc:
        status = "ERROR"
        error_type = type(exc).__name__
        error = str(exc)[:1000]
        raise
    finally:
        recorder.append({
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "name": name,
            "kind": kind,
            "started_at": started_at,
            "ended_at": _utc_now(),
            "duration_ms": round((time.perf_counter() - started_perf) * 1000, 3),
            "status": status,
            "error_type": error_type,
            "error": error,
            "attributes": dict(attributes or {}),
        })
        _ACTIVE_SPAN_ID.reset(token)


def record_completed_span(
    *,
    name: str,
    kind: str,
    status: str,
    started_at: Optional[str] = None,
    ended_at: Optional[str] = None,
    duration_ms: Optional[float] = None,
    attributes: Optional[Mapping[str, Any]] = None,
    error_type: Optional[str] = None,
    error: Optional[str] = None,
    span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
) -> Optional[str]:
    recorder = _ACTIVE_TRACE.get()
    if recorder is None:
        return None
    completed_span_id = span_id or uuid4().hex
    recorder.append({
        "span_id": completed_span_id,
        "parent_span_id": parent_span_id or _ACTIVE_SPAN_ID.get() or recorder.root_span_id,
        "name": name,
        "kind": kind,
        "started_at": started_at or _utc_now(),
        "ended_at": ended_at or _utc_now(),
        "duration_ms": duration_ms,
        "status": status,
        "error_type": error_type,
        "error": error,
        "attributes": dict(attributes or {}),
    })
    return completed_span_id


def traced_node(name: str, node: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a synchronous LangGraph node without changing its contract."""

    @wraps(node)
    def wrapped(state, *args, **kwargs):
        attributes = {
            "ticker": state.get("company_of_interest") if isinstance(state, dict) else None,
            "trade_date": state.get("trade_date") if isinstance(state, dict) else None,
        }
        with trace_span(name, "graph_node", attributes=attributes):
            return node(state, *args, **kwargs)

    return wrapped


def write_trace(path: str | Path, trace: Optional[Mapping[str, Any]] = None) -> Path:
    """Atomically persist a trace snapshot."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(trace or get_trace_snapshot())
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target
