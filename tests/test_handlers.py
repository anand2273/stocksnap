from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import handlers
from utils import NewsItem, StockLookupError, StockSnapshot


def make_update():
    message = SimpleNamespace(
        reply_text=AsyncMock(),
        reply_photo=AsyncMock(),
    )
    return SimpleNamespace(effective_message=message), message


def make_snapshot():
    return StockSnapshot(
        symbol="AAPL",
        name="Apple & Co",
        price=201.25,
        market_cap=3_100_000_000_000,
        forward_pe=28.1,
        trailing_pe=31.2,
        year_high=220.0,
        year_low=165.0,
        trailing_eps=6.45,
        target_price=225.0,
        news=(NewsItem("Apple <news>", "https://example.com/apple?a=1&b=2"),),
        chart=BytesIO(b"chart"),
    )


@pytest.mark.asyncio
async def test_start_describes_usage_and_disclaimer():
    update, message = make_update()

    await handlers.start(update, SimpleNamespace())

    text = message.reply_text.await_args.args[0]
    assert "/stock AAPL" in text
    assert "not financial advice" in text


@pytest.mark.asyncio
async def test_stock_without_ticker_stops_after_usage_message(monkeypatch):
    update, message = make_update()
    lookup = monkeypatch.setattr(
        handlers,
        "get_stock_snapshot",
        lambda _: pytest.fail("lookup should not run"),
    )

    await handlers.stock(update, SimpleNamespace(args=[]))

    del lookup
    message.reply_text.assert_awaited_once()
    message.reply_photo.assert_not_awaited()


@pytest.mark.asyncio
async def test_stock_sends_chart_and_safely_formatted_report(monkeypatch):
    update, message = make_update()
    monkeypatch.setattr(handlers, "get_stock_snapshot", lambda _: make_snapshot())

    await handlers.stock(update, SimpleNamespace(args=["aapl"]))

    message.reply_photo.assert_awaited_once()
    message.reply_text.assert_awaited_once()
    report = message.reply_text.await_args.args[0]
    assert "STONKSY REPORT" in report
    assert "Apple &amp; Co" in report
    assert "Apple &lt;news&gt;" in report
    assert "Schedule reminder" not in report
    markup = message.reply_text.await_args.kwargs["reply_markup"]
    assert markup.inline_keyboard[0][0].url == "https://finance.yahoo.com/quote/AAPL"


@pytest.mark.asyncio
async def test_stock_returns_expected_lookup_error(monkeypatch):
    update, message = make_update()

    def fail_lookup(_):
        raise StockLookupError("No market data was found for NOPE.")

    monkeypatch.setattr(handlers, "get_stock_snapshot", fail_lookup)

    await handlers.stock(update, SimpleNamespace(args=["NOPE"]))

    message.reply_text.assert_awaited_once_with("No market data was found for NOPE.")
    message.reply_photo.assert_not_awaited()
