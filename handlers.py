# file mainly for command handlers and functions 
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from utils import get_quote, get_overview, get_news, get_stock, get_plot, escape_md, safe_escape_md, format_market_cap, get_earnings_date
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text="Welcome to Stonksy, " \
                                   "your favourite stock companion! " \
                                   "Use /stock (ticker) to begin.")
    
async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        await update.message.reply_text("Usage: /stock <ticker>. (e.g. /stock AAPL)")
    symbol = context.args[0].upper()

    # !!USING PAID APIs. KEEP RUNNING OUT OF FREE CALLS, IMPOSSIBLE TO TEST!!
    # loop = asyncio.get_event_loop()
    # quote_task = loop.run_in_executor(executor, get_quote, symbol)
    # overview_task = loop.run_in_executor(executor, get_overview, symbol)
    # news_task = loop.run_in_executor(executor, get_news, symbol)

    # quote, overview, latest_news = await asyncio.gather(quote_task, overview_task, news_task)

    # name = overview.get("Name")
    # price = quote.get("c")
    # mktcap = overview.get("MarketCapitalization")
    # fwdPE = overview.get("ForwardPE")
    # trailingPE = overview.get("TrailingPE")
    # hi, lo = overview.get("52WeekHigh"), overview.get("52WeekHigh")
    # eps = overview.get("EPS")
    # arsb, arb, arh, ars, arss = overview.get("AnalystRatingStrongBuy"), overview.get("AnalystRatingBuy"), overview.get("AnalystRatingHold"), overview.get("AnalystRatingSell"), overview.get("AnalystRatingStrongSell")
    # tgt = overview.get("AnalystTargetPrice")
    # news_text = "\n".join([f"- {article.get('title')}\n{article.get('url')}" for article in latest_news])

    try:
        stock = get_stock(symbol)
        plot = get_plot(symbol)
        info = stock.info
    except Exception as e:
        print(e)
        await update.message.reply_text(text=escape_md(str(e)),
                                       parse_mode="MarkdownV2")
        return
    
    print(info)

    latest_news = [a.get("content") for a in stock.news[:5] if a and a.get("content")]

    name = safe_escape_md(info.get("shortName"))
    price = safe_escape_md(info.get("regularMarketPrice"))
    plot = get_plot(symbol)
    mktcap = escape_md(format_market_cap(info.get("marketCap", "N/A")))
    fwdPE = safe_escape_md(info.get("forwardPE"))
    trailingPE = safe_escape_md(info.get("trailingPE"))
    hi, lo = safe_escape_md(info.get("fiftyTwoWeekHigh")), safe_escape_md(info.get("fiftyTwoWeekLow"))
    eps = safe_escape_md(info.get("trailingEPS"))
    # (this is a finnhub only thing) arsb, arb, arh, ars, arss = overview.get("AnalystRatingStrongBuy"), overview.get("AnalystRatingBuy"), overview.get("AnalystRatingHold"), overview.get("AnalystRatingSell"), overview.get("AnalystRatingStrongSell"))
    tgt = safe_escape_md(info.get("targetMeanPrice"))

    news_text = "\n"
    for article in latest_news[:3]:
        summary = article.get("summary")
        if not summary:
            continue
        x = article.get("clickThroughUrl")
        if not x:
            continue
        url = x.get("url")
        if not url:
            continue

        news_text += f"{safe_escape_md(summary)}\n{safe_escape_md(url)}\n\n"

    message = (
            f"🗞️*𝗦𝗧𝗢𝗡𝗞𝗦𝗬 𝗥𝗘𝗣𝗢𝗥𝗧: {name}*🗞️\n\n"
            f"💰 *Current Price:* ${price}\n\n"
            f"💸 *Market Cap:* ${mktcap}\n\n"
            f"📈 *Forward P/E:* {fwdPE}\n\n"
            f"🧐 *Trailing P/E:* {trailingPE}\n\n"
            f"📊 *52 Week High/Low:* ${hi} / ${lo}\n\n"
            f"🪙 *EPS:* {eps}\n\n"
            f"🤑 *Target Price:* ${tgt}\n\n"
            # f"🥸 *Analyst Ratings (Buy/Hold/Sell):* {arsb + arb} / {arh} / {ars + arss}\n\n"
            f"🚨 *Latest News:* 🚨\n{news_text}"
            )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("View balance sheet on Yahoo Finance!", url=f"https://finance.yahoo.com/quote/{symbol}/balance-sheet"),
            InlineKeyboardButton("Schedule reminder for Earnings Report", callback_data=f"schedule_earnings_{symbol}")  
        ]
    ])

    await context.bot.send_photo(chat_id=update.effective_chat.id,
                                   photo=plot,
                                   caption=f"{name}'s Last Month Price Chart",
                                   parse_mode="MarkdownV2"
                                   )
    
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=message,
                                   parse_mode="MarkdownV2",
                                   reply_markup=keyboard)
    
async def earnings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    ticker = data.partition("schedule_earnings_")[2]
    earnings_date = get_earnings_date(ticker)

    # set_earnings_reminder(ticker)
    message = escape_md(f"Earnings reminder has beens set! The next report is scheduled for {earnings_date}")
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=message,
                                   parse_mode="MarkdownV2")
    

