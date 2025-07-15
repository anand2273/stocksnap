# for services like API calls and fetching data from wherever
import os
import finnhub as fin
import requests
from dotenv import load_dotenv
from datetime import date
from cachetools import TTLCache, cached
import yfinance as yf
import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO

load_dotenv()
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
AV_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

# caches
price_cache = TTLCache(maxsize=100, ttl=1800)
overview_cache = TTLCache(maxsize=100, ttl=1800)
news_cache = TTLCache(maxsize=100, ttl=1800)

client = fin.Client(api_key=f"{FINNHUB_API_KEY}")

# API CALLS - PAYWALL PRESENT
#error handling for API fetches

# mainly for price
@cached(price_cache)
def get_quote(ticker: str) -> dict:
    print("quote api call was made")
    return client.quote(ticker)


# contains trailing PE, forward PE, Description, Analyst Ratings, Analyst Target Price, Market Cap, 52 week highs and lows
@cached(overview_cache)
def get_overview(ticker: str) -> dict:
    resp = requests.get("https://www.alphavantage.co/query", {
                        "function": "OVERVIEW",
                        "symbol": ticker,
                        "apikey": AV_API_KEY
                        })
    data = resp.json()
    print("overview api call was made")
    return data

@cached(news_cache)
def get_news(ticker: str) -> dict:
    resp = requests.get("https://www.alphavantage.co/query", {
                        "function":"NEWS_SENTIMENT",
                        "tickers": ticker,
                        "sort": "RELEVANCE", "LATEST"
                        "limit": "0",
                        "apikey": AV_API_KEY
                        })
    data = resp.json()
    feed = data.get("feed", [])[:3]
    print("news api call was made")
    return feed

# API CALLS - YFINANCE (inferior)

def get_stock(ticker: str) -> dict:
    ticker = ticker.upper()
    stock = yf.Ticker(ticker)
    if not stock.info.get("shortName"):
       raise Exception("Ticker not found. Please enter the correct ticker.") 
    print("inferior yfinance api was called")
    return stock

def get_plot(ticker: str) -> dict:
    ticker = ticker.upper()
    stock = yf.Ticker(ticker)
    if not stock.info.get("shortName"):
        raise Exception("Ticker not found. Please enter the correct ticker")

    hist = stock.history(period="1mo")
    name = stock.info.get("shortName")
    print("API WAS SUCCESSFULLY CALLED WHILE PLOTTING. although inferior")

    #plotting
    plt.figure(figsize=(10,4))
    plt.plot(hist.index, hist["Close"], label="Close Price", linewidth=2)
    plt.title(f"{name}'s Last Month Price Movement")
    plt.xlabel("Date")
    plt.ylabel("Close Price ($)")
    plt.grid(True)
    plt.gca().xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))  # Tick per week
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    plt.xticks(rotation=45)

    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    return buf

def get_earnings_date(ticker: str):
    ticker = ticker.upper()
    stock = yf.Ticker(ticker)
    earnings_date = stock.calendar.get("Earnings Date")[0]
    return earnings_date

print(get_earnings_date("AAPL"))

# Formatting and other misc functions
def escape_md(text):
    if not isinstance(text, str):
        return ""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

def safe_escape_md(val):
    return escape_md(f"{val:.2f}") if isinstance(val, (int, float)) else escape_md(str(val) if val is not None else "N/A")

def format_market_cap(val):
    if type(val) == str:
        return val
    val = float(val)
    for unit in ['','K','M','B','T','Q']:
        if abs(val) < 1000.0:
            return f"{val:.2f}{unit}"
        val /= 1000.0
    return f"{val:.2f}Q"
