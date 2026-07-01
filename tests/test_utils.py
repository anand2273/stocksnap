from io import BytesIO
from types import SimpleNamespace

import pandas as pd
import pytest

from utils import (
    StockLookupError,
    _extract_news,
    _price_axis_limits,
    create_price_chart,
    format_market_cap,
    format_number,
    get_stock_snapshot,
    normalize_ticker,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" aapl ", "AAPL"),
        ("BRK-B", "BRK-B"),
        ("^gspc", "^GSPC"),
        ("BTC-USD", "BTC-USD"),
    ],
)
def test_normalize_ticker(raw, expected):
    assert normalize_ticker(raw) == expected


@pytest.mark.parametrize("raw", ["", "bad ticker", "A" * 16, "AAPL/../../"])
def test_normalize_ticker_rejects_invalid_values(raw):
    with pytest.raises(StockLookupError):
        normalize_ticker(raw)


def test_number_formatting_handles_real_and_missing_values():
    assert format_number(1234.567) == "1,234.57"
    assert format_number(None) == "N/A"
    assert format_number(float("nan")) == "N/A"


def test_market_cap_formatting():
    assert format_market_cap(2_500_000_000) == "2.50B"
    assert format_market_cap(None) == "N/A"
    assert format_market_cap(float("inf")) == "N/A"


def test_price_axis_tracks_observed_range_instead_of_zero():
    minimum, maximum = _price_axis_limits([198.0, 200.0, 202.0])

    assert minimum == pytest.approx(197.52)
    assert maximum == pytest.approx(202.48)
    assert minimum > 0


def test_price_axis_gives_flat_data_visible_padding():
    minimum, maximum = _price_axis_limits([100.0, 100.0])

    assert minimum == 99.0
    assert maximum == 101.0


def test_extract_news_supports_nested_yahoo_payload_and_filters_urls():
    raw_news = [
        {
            "content": {
                "title": "Useful headline",
                "clickThroughUrl": {"url": "https://example.com/story"},
            }
        },
        {
            "content": {
                "title": "Unsafe link",
                "clickThroughUrl": {"url": "javascript:alert(1)"},
            }
        },
        None,
    ]

    news = _extract_news(raw_news)

    assert len(news) == 1
    assert news[0].title == "Useful headline"
    assert news[0].url == "https://example.com/story"


def test_create_price_chart_returns_png_buffer():
    history = pd.DataFrame(
        {"Close": [100.0, 103.0, 101.5]},
        index=pd.date_range("2026-01-01", periods=3),
    )

    chart = create_price_chart("TEST", "Test Corp", history)

    assert isinstance(chart, BytesIO)
    assert chart.read(8) == b"\x89PNG\r\n\x1a\n"


def test_get_stock_snapshot_uses_one_ticker_and_tolerates_news_failure(monkeypatch):
    history = pd.DataFrame(
        {"Close": [100.0, 101.0]},
        index=pd.date_range("2026-01-01", periods=2),
    )

    class FakeTicker:
        info = {
            "shortName": "Example Corp",
            "regularMarketPrice": 101.0,
            "marketCap": 1_000_000,
        }

        def history(self, period, raise_errors):
            assert period == "1mo"
            assert raise_errors is True
            return history

        fast_info = {}

        @property
        def news(self):
            raise RuntimeError("news temporarily unavailable")

    ticker_factory = SimpleNamespace(calls=0)

    def fake_ticker(symbol):
        ticker_factory.calls += 1
        assert symbol == "TEST"
        return FakeTicker()

    monkeypatch.setattr("utils.yf.Ticker", fake_ticker)

    snapshot = get_stock_snapshot("test")

    assert ticker_factory.calls == 1
    assert snapshot.symbol == "TEST"
    assert snapshot.name == "Example Corp"
    assert snapshot.news == ()
    assert snapshot.chart.read(8) == b"\x89PNG\r\n\x1a\n"


def test_get_stock_snapshot_falls_back_when_fundamentals_are_empty(monkeypatch):
    history = pd.DataFrame(
        {"Close": [199.0, 201.0]},
        index=pd.date_range("2026-01-01", periods=2),
    )

    class FakeTicker:
        @property
        def info(self):
            raise RuntimeError("empty fundamentals response")

        fast_info = {
            "lastPrice": 201.0,
            "marketCap": 3_000_000_000_000,
            "yearHigh": 220.0,
            "yearLow": 165.0,
        }
        news = []

        def history(self, period, raise_errors):
            assert period == "1mo"
            assert raise_errors is True
            return history

    monkeypatch.setattr("utils.yf.Ticker", lambda _: FakeTicker())

    snapshot = get_stock_snapshot("AAPL")

    assert snapshot.name == "AAPL"
    assert snapshot.price == 201.0
    assert snapshot.market_cap == 3_000_000_000_000
    assert snapshot.year_high == 220.0
    assert snapshot.forward_pe is None
