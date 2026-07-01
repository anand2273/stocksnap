import asyncio
import html
import logging
from urllib.parse import quote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from utils import (
    StockLookupError,
    StockSnapshot,
    format_market_cap,
    format_number,
    get_stock_snapshot,
    normalize_ticker,
)

LOGGER = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "<b>Welcome to Stonksy.</b>\n\n"
    "Get a concise market snapshot directly in Telegram:\n"
    "<code>/stock AAPL</code>\n\n"
    "Stonksy provides market information for research and education—not financial advice. "
    "Quotes may be delayed."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.effective_message:
        await update.effective_message.reply_text(
            WELCOME_MESSAGE,
            parse_mode=ParseMode.HTML,
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


def _report_message(snapshot: StockSnapshot) -> str:
    name = html.escape(snapshot.name)
    symbol = html.escape(snapshot.symbol)
    news_lines = []
    for item in snapshot.news:
        title = html.escape(item.title)
        url = html.escape(item.url, quote=True)
        news_lines.append(f'• <a href="{url}">{title}</a>')

    news = "\n".join(news_lines) if news_lines else "No recent articles available."
    return (
        f"<b>STONKSY REPORT · {name} ({symbol})</b>\n\n"
        f"💰 <b>Price:</b> ${format_number(snapshot.price)}\n"
        f"💸 <b>Market cap:</b> ${format_market_cap(snapshot.market_cap)}\n"
        f"📈 <b>Forward P/E:</b> {format_number(snapshot.forward_pe)}\n"
        f"🧐 <b>Trailing P/E:</b> {format_number(snapshot.trailing_pe)}\n"
        f"📊 <b>52-week range:</b> ${format_number(snapshot.year_low)} – "
        f"${format_number(snapshot.year_high)}\n"
        f"🪙 <b>EPS:</b> {format_number(snapshot.trailing_eps)}\n"
        f"🎯 <b>Analyst target:</b> ${format_number(snapshot.target_price)}\n\n"
        f"<b>Latest news</b>\n{news}\n\n"
        "<i>Market data may be delayed. For informational purposes only.</i>"
    )


async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    if not context.args:
        await message.reply_text("Usage: /stock <ticker> — for example, /stock AAPL")
        return

    try:
        symbol = normalize_ticker(context.args[0])
    except StockLookupError as exc:
        await message.reply_text(str(exc))
        return

    try:
        snapshot = await asyncio.to_thread(get_stock_snapshot, symbol)
    except StockLookupError as exc:
        await message.reply_text(str(exc))
        return
    except Exception:
        LOGGER.exception("Unexpected stock lookup failure for %s", symbol)
        await message.reply_text(
            "Stonksy could not load that ticker right now. Please try again shortly."
        )
        return

    yahoo_symbol = quote(snapshot.symbol, safe="")
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "View on Yahoo Finance",
                    url=f"https://finance.yahoo.com/quote/{yahoo_symbol}",
                )
            ]
        ]
    )

    await message.reply_photo(
        photo=snapshot.chart,
        caption=f"{html.escape(snapshot.name)} · one-month closing price",
        parse_mode=ParseMode.HTML,
    )
    await message.reply_text(
        _report_message(snapshot),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    LOGGER.error("Unhandled Telegram update error", exc_info=context.error)
