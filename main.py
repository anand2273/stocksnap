import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackContext
from telegram import Update
from aiohttp import web

# Load env vars
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Set this in Render

# Create Telegram app
bot_app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Bot is live via webhook!")

bot_app.add_handler(CommandHandler("start", start))

# Webhook handler
async def webhook_handler(request):
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return web.Response()

# AIOHTTP setup
web_app = web.Application()
web_app.router.add_post("/webhook", webhook_handler)

# Main Entry
if __name__ == "__main__":
    import asyncio

    async def main():
        await bot_app.bot.delete_webhook()
        await bot_app.bot.set_webhook(url=WEBHOOK_URL)
        print("Webhook set!")

    asyncio.run(main())

    PORT = int(os.environ.get("PORT", 8000))
    web.run_app(web_app, host="0.0.0.0", port=PORT)
