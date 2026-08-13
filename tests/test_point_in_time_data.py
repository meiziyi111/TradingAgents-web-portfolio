"""Offline guards for historical data boundaries."""

from unittest.mock import patch

import pandas as pd
import pytest

from tradingagents.dataflows.stockstats_utils import load_ohlcv
from tradingagents.dataflows.y_finance import get_fundamentals


@pytest.mark.unit
def test_indicator_ohlcv_is_cut_off_at_as_of_date():
    index = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
    frame = pd.DataFrame({
        "Open": [1, 2, 3], "High": [1, 2, 3], "Low": [1, 2, 3],
        "Close": [1, 2, 3], "Volume": [10, 20, 30],
    }, index=index)
    frame.index.name = "Date"
    with patch("tradingagents.dataflows.stockstats_utils.yf.download", return_value=frame) as download:
        result = load_ohlcv("NVDA", "2025-01-02")
    assert result["Date"].max() <= pd.Timestamp("2025-01-02")
    assert download.call_args.kwargs["end"] == "2025-01-03"


@pytest.mark.unit
def test_current_snapshot_fundamentals_blocked_for_historical_run():
    with patch("tradingagents.dataflows.y_finance.yf.Ticker") as ticker:
        result = get_fundamentals("NVDA", "2025-01-02")
    assert "not point-in-time safe" in result
    ticker.assert_not_called()
