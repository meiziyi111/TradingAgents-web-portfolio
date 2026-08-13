"""Tool provenance and safe fallback tests."""

import pytest

import tradingagents.dataflows.interface as interface
from tradingagents.dataflows.provenance import get_tool_trace, reset_tool_trace


@pytest.mark.unit
def test_vendor_fallback_records_error_and_success(monkeypatch):
    reset_tool_trace()
    monkeypatch.setattr(interface, "get_vendor", lambda *args: "yfinance")
    monkeypatch.setitem(interface.VENDOR_METHODS, "get_stock_data", {
        "yfinance": lambda *args: (_ for _ in ()).throw(RuntimeError("primary down")),
        "alpha_vantage": lambda *args: "fallback data",
    })
    result = interface.route_to_vendor("get_stock_data", "NVDA", "2025-01-01", "2025-01-02")
    trace = get_tool_trace()
    assert result == "fallback data"
    assert [row["status"] for row in trace] == ["ERROR", "SUCCESS"]
    assert trace[-1]["output_sha256"]


@pytest.mark.unit
def test_persisted_tool_error_redacts_api_key(monkeypatch):
    reset_tool_trace()
    monkeypatch.setattr(interface, "get_vendor", lambda *args: "yfinance")
    monkeypatch.setitem(interface.VENDOR_METHODS, "get_stock_data", {
        "yfinance": lambda *args: (_ for _ in ()).throw(
            RuntimeError("https://example.test?apikey=SECRET123&x=1")
        ),
    })
    with pytest.raises(RuntimeError):
        interface.route_to_vendor("get_stock_data", "NVDA", "2025-01-01", "2025-01-02")
    error = get_tool_trace()[0]["error"]
    assert "SECRET123" not in error
    assert "apikey=REDACTED" in error
