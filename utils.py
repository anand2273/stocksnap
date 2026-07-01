import logging
import re
from dataclasses import dataclass
from io import BytesIO
from math import isfinite
from numbers import Real
from urllib.parse import urlparse

import matplotlib
import yfinance as yf

matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

TICKER_PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.^=-]{0,14}$")
LOGGER = logging.getLogger(__name__)


class StockLookupError(ValueError):
    """Raised when a ticker is invalid or market data is unavailable."""


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str


@dataclass(frozen=True)
class StockSnapshot:
    symbol: str
    name: str
    price: object
    market_cap: object
    forward_pe: object
    trailing_pe: object
    year_high: object
    year_low: object
    trailing_eps: object
    target_price: object
    news: tuple[NewsItem, ...]
    chart: BytesIO


def normalize_ticker(ticker: str) -> str:
    symbol = ticker.strip().upper()
    if not TICKER_PATTERN.fullmatch(symbol):
        raise StockLookupError(
            "Enter a valid ticker using up to 15 letters, numbers, '.', '-', '^', or '='."
        )
    return symbol


def format_number(value: object) -> str:
    if (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and isfinite(float(value))
    ):
        return f"{float(value):,.2f}"
    return "N/A"


def format_market_cap(value: object) -> str:
    if (
        not isinstance(value, Real)
        or isinstance(value, bool)
        or not isfinite(float(value))
    ):
        return "N/A"

    amount = float(value)
    for unit in ("", "K", "M", "B", "T", "Q"):
        if abs(amount) < 1000:
            return f"{amount:,.2f}{unit}"
        amount /= 1000
    return f"{amount:,.2f}Q"


def _valid_http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _extract_news(raw_news: object) -> tuple[NewsItem, ...]:
    if not isinstance(raw_news, list):
        return ()

    articles: list[NewsItem] = []
    for raw_article in raw_news:
        if not isinstance(raw_article, dict):
            continue
        article = raw_article.get("content") or raw_article
        if not isinstance(article, dict):
            continue

        title = article.get("title") or article.get("summary")
        link = article.get("clickThroughUrl") or article.get("canonicalUrl")
        url = link.get("url") if isinstance(link, dict) else link
        valid_url = _valid_http_url(url)
        if isinstance(title, str) and title.strip() and valid_url:
            articles.append(NewsItem(title=title.strip(), url=valid_url))
        if len(articles) == 3:
            break
    return tuple(articles)


def _fast_info_value(fast_info: object, *keys: str) -> object:
    for key in keys:
        try:
            if hasattr(fast_info, "get"):
                value = fast_info.get(key)
            else:
                value = getattr(fast_info, key)
        except Exception:
            continue
        if value is not None:
            return value
    return None


def _price_axis_limits(values: object) -> tuple[float, float]:
    finite_values = [
        float(value)
        for value in values
        if isinstance(value, Real) and isfinite(float(value))
    ]
    if not finite_values:
        raise StockLookupError("No valid closing prices were returned.")

    minimum = min(finite_values)
    maximum = max(finite_values)
    spread = maximum - minimum
    padding = spread * 0.12 if spread else max(abs(maximum) * 0.01, 1.0)
    return minimum - padding, maximum + padding


def create_price_chart(symbol: str, name: str, history: object) -> BytesIO:
    if history is None or getattr(history, "empty", True) or "Close" not in history:
        raise StockLookupError(f"No recent price history was found for {symbol}.")

    close_prices = history["Close"].dropna()
    y_minimum, y_maximum = _price_axis_limits(close_prices)

    figure, axis = plt.subplots(figsize=(10, 4.8))
    figure.patch.set_facecolor("#F8FAFC")
    axis.set_facecolor("#F8FAFC")
    axis.plot(close_prices.index, close_prices, color="#16A34A", linewidth=2.5)
    axis.fill_between(
        close_prices.index,
        close_prices,
        y_minimum,
        alpha=0.08,
        color="#16A34A",
    )
    axis.set_ylim(y_minimum, y_maximum)
    axis.set_title(
        f"{name} · one-month closing price",
        loc="left",
        fontsize=15,
        fontweight="bold",
        color="#0F172A",
        pad=14,
    )
    axis.set_ylabel("Price (USD)", color="#475569")
    axis.grid(axis="y", color="#CBD5E1", alpha=0.55, linewidth=0.8)
    axis.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    axis.tick_params(colors="#475569")
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.spines["bottom"].set_color("#CBD5E1")
    figure.autofmt_xdate(rotation=0)
    figure.tight_layout()

    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    plt.close(figure)
    buffer.seek(0)
    return buffer


def get_stock_snapshot(ticker: str) -> StockSnapshot:
    symbol = normalize_ticker(ticker)
    stock = yf.Ticker(symbol)

    try:
        history = stock.history(period="1mo", raise_errors=True)
    except Exception as exc:
        LOGGER.exception("Yahoo Finance price-history lookup failed for %s", symbol)
        raise StockLookupError(
            f"Stonksy could not load {symbol}. Check the ticker and try again."
        ) from exc

    try:
        raw_info = stock.info
        info = raw_info if isinstance(raw_info, dict) else {}
    except Exception:
        LOGGER.warning(
            "Yahoo Finance fundamentals lookup failed for %s; using fast-info fallback",
            symbol,
            exc_info=True,
        )
        info = {}

    try:
        fast_info = stock.fast_info
    except Exception:
        LOGGER.warning("Yahoo Finance fast-info lookup failed for %s", symbol, exc_info=True)
        fast_info = {}

    try:
        raw_news = stock.news
    except Exception:
        LOGGER.info("Yahoo Finance news lookup failed for %s", symbol, exc_info=True)
        raw_news = []

    raw_name = info.get("shortName") or info.get("longName")
    name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else symbol
    chart = create_price_chart(symbol, name, history)
    return StockSnapshot(
        symbol=symbol,
        name=name,
        price=(
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or _fast_info_value(fast_info, "last_price", "lastPrice")
        ),
        market_cap=(
            info.get("marketCap")
            or _fast_info_value(fast_info, "market_cap", "marketCap")
        ),
        forward_pe=info.get("forwardPE"),
        trailing_pe=info.get("trailingPE"),
        year_high=(
            info.get("fiftyTwoWeekHigh")
            or _fast_info_value(fast_info, "year_high", "yearHigh")
        ),
        year_low=(
            info.get("fiftyTwoWeekLow")
            or _fast_info_value(fast_info, "year_low", "yearLow")
        ),
        trailing_eps=info.get("trailingEPS"),
        target_price=info.get("targetMeanPrice"),
        news=_extract_news(raw_news),
        chart=chart,
    )
