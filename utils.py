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


def create_price_chart(symbol: str, name: str, history: object) -> BytesIO:
    if history is None or getattr(history, "empty", True) or "Close" not in history:
        raise StockLookupError(f"No recent price history was found for {symbol}.")

    figure, axis = plt.subplots(figsize=(10, 4.8))
    figure.patch.set_facecolor("#F8FAFC")
    axis.set_facecolor("#F8FAFC")
    axis.plot(history.index, history["Close"], color="#16A34A", linewidth=2.5)
    axis.fill_between(
        history.index,
        history["Close"],
        alpha=0.08,
        color="#16A34A",
    )
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
    try:
        stock = yf.Ticker(symbol)
        info = stock.info or {}
        history = stock.history(period="1mo")
    except Exception as exc:
        raise StockLookupError(
            f"Stonksy could not load {symbol}. Check the ticker and try again."
        ) from exc

    name = info.get("shortName") if isinstance(info, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise StockLookupError(f"No market data was found for {symbol}.")

    try:
        raw_news = stock.news
    except Exception:
        raw_news = []

    chart = create_price_chart(symbol, name, history)
    return StockSnapshot(
        symbol=symbol,
        name=name.strip(),
        price=info.get("regularMarketPrice") or info.get("currentPrice"),
        market_cap=info.get("marketCap"),
        forward_pe=info.get("forwardPE"),
        trailing_pe=info.get("trailingPE"),
        year_high=info.get("fiftyTwoWeekHigh"),
        year_low=info.get("fiftyTwoWeekLow"),
        trailing_eps=info.get("trailingEPS"),
        target_price=info.get("targetMeanPrice"),
        news=_extract_news(raw_news),
        chart=chart,
    )
