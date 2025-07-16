import logging, os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
from handlers import start, stock, earnings_callback_handler

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

application = ApplicationBuilder().token(BOT_TOKEN).build()
 
start_handler = CommandHandler('start', start)
stock_handler = CommandHandler('stock', stock)
earnings_scheduling_handler = CallbackQueryHandler(earnings_callback_handler, pattern=r"^schedule_earnings_")

application.add_handler(start_handler)
application.add_handler(stock_handler)
application.add_handler(earnings_scheduling_handler)

if __name__ == '__main__':
    application.run_polling()