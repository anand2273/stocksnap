import os
from dotenv import load_dotenv
from telegram.ext import Application
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from aiohttp import web

# Load env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = f"https://your-app-name.onrender.com/webhook"

# Your bot handlers
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Bot is live via webhook!")

# Create the app
bot_app = Application.builder().token(TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))

# Webhook handler for Telegram
async def webhook_handler(request):
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return web.Response()

# aiohttp server
web_app = web.Application()
web_app.router.add_post("/webhook", webhook_handler)

# Main Entry Point
if __name__ == "__main__":
    import asyncio
    async def main():
        await bot_app.bot.delete_webhook()
        await bot_app.bot.set_webhook(url=WEBHOOK_URL)
        print("Webhook set!")

    asyncio.run(main())

    # Start aiohttp server (this is where Render sees port 8000 open)
    web.run_app(web_app, host="0.0.0.0", port=8000)
