import time
import logging

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError
from stockstats import wrap
from typing import Annotated
import os
from .config import get_config
from .utils import safe_ticker_component

logger = logging.getLogger(__name__)


def yf_retry(func, max_retries=3, base_delay=2.0):
    """Execute a yfinance call with exponential backoff on rate limits.

    yfinance raises YFRateLimitError on HTTP 429 responses but does not
    retry them internally. This wrapper adds retry logic specifically
    for rate limits. Other exceptions propagate immediately.
    """
    for attempt in range(max_retries + 1):
        try:
            return func()
        except YFRateLimitError:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Yahoo Finance rate limited, retrying in {delay:.0f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                raise


def _clean_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize a stock DataFrame for stockstats: parse dates, fill price gaps.

    Fills NaN prices before dropping rows so a trading day whose Close
    hasn't been finalized by the data provider (common with yfinance for
    the most recent session) is preserved with the last known value.
    """
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"])

    price_cols = [c for c in ["Open", "High", "Low", "Close"] if c in data.columns]
    data[price_cols] = data[price_cols].apply(pd.to_numeric, errors="coerce")
    # Forward fill uses only information already observed. Back-filling is
    # prohibited because it can copy a future price into an earlier row.
    data[price_cols] = data[price_cols].ffill()
    if "Volume" in data.columns:
        data["Volume"] = pd.to_numeric(data["Volume"], errors="coerce")
    data = data.dropna(subset=["Close"])

    return data


def load_ohlcv(symbol: str, curr_date: str) -> pd.DataFrame:
    """Fetch OHLCV data directly from yfinance.

    Always downloads fresh data (no caching) and returns all available
    rows so the analysis always uses the latest market prices.
    """
    safe_ticker_component(symbol)  # validate ticker

    cutoff = pd.Timestamp(curr_date).normalize()
    start_date = cutoff - pd.DateOffset(years=5)
    end_date = cutoff + pd.Timedelta(days=1)
    data = yf_retry(lambda: yf.download(
        symbol,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        multi_level_index=False,
        progress=False,
        auto_adjust=True,
    ))
    data = data.reset_index()
    data = _clean_dataframe(data)
    data = data[data["Date"].dt.normalize() <= cutoff]
    return data


def filter_financials_by_date(
    data: pd.DataFrame,
    curr_date: str,
    availability_lag_days: int = 0,
) -> pd.DataFrame:
    """Drop financial statement columns (fiscal period timestamps) after curr_date.

    yfinance financial statements use fiscal period end dates as columns.
    Columns after curr_date represent future data and are removed to
    prevent look-ahead bias.
    """
    if not curr_date or data.empty:
        return data
    # yfinance columns are fiscal-period ends, not filing timestamps. Apply an
    # explicit conservative lag so a period is not treated as public on the
    # day it ends. This remains an approximation, not true point-in-time data.
    cutoff = pd.Timestamp(curr_date) - pd.Timedelta(days=availability_lag_days)
    mask = pd.to_datetime(data.columns, errors="coerce") <= cutoff
    return data.loc[:, mask]


class StockstatsUtils:
    @staticmethod
    def get_stock_stats(
        symbol: Annotated[str, "ticker symbol for the company"],
        indicator: Annotated[
            str, "quantitative indicators based off of the stock data for the company"
        ],
        curr_date: Annotated[
            str, "curr date for retrieving stock price data, YYYY-mm-dd"
        ],
    ):
        data = load_ohlcv(symbol, curr_date)
        df = wrap(data)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        curr_date_str = pd.to_datetime(curr_date).strftime("%Y-%m-%d")

        df[indicator]  # trigger stockstats to calculate the indicator
        matching_rows = df[df["Date"].str.startswith(curr_date_str)]

        if not matching_rows.empty:
            indicator_value = matching_rows[indicator].values[0]
            return indicator_value
        else:
            return "N/A: Not a trading day (weekend or holiday)"
