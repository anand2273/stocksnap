import hashlib
import logging
import os
import re
import secrets
from collections.abc import AsyncIterator

from aiohttp import web
from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler

from handlers import error_handler, help_command, start, stock

load_dotenv()

LOGGER = logging.getLogger(__name__)
WEBHOOK_PATH = "/telegram/webhook"
HEALTH_PATH = "/health"
TELEGRAM_SECRET_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


def create_application(token: str) -> Application:
    """Build the Telegram application and register all public commands."""
    if not token:
        raise RuntimeError("BOT_TOKEN is required.")

    application = ApplicationBuilder().token(token).post_init(configure_bot).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stock", stock))
    application.add_error_handler(error_handler)
    return application


async def configure_bot(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("stock", "Get a market snapshot, e.g. /stock AAPL"),
            BotCommand("help", "Show usage and data notes"),
        ]
    )


def normalize_webhook_secret(value: str) -> str:
    """Return a Telegram-compatible secret without weakening generated values."""
    if not value:
        raise RuntimeError("WEBHOOK_SECRET is required in webhook mode.")
    if TELEGRAM_SECRET_PATTERN.fullmatch(value):
        return value
    return hashlib.sha256(value.encode()).hexdigest()


def create_web_app(
    telegram_application: Application,
    webhook_secret: str,
    webhook_url: str,
    *,
    manage_lifecycle: bool = True,
) -> web.Application:
    """Create the HTTP service used by Render and Telegram."""
    webhook_secret = normalize_webhook_secret(webhook_secret)

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def telegram_webhook(request: web.Request) -> web.Response:
        supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not secrets.compare_digest(supplied_secret, webhook_secret):
            return web.json_response({"error": "forbidden"}, status=403)

        try:
            payload = await request.json()
            update = Update.de_json(payload, telegram_application.bot)
            if not isinstance(update, Update):
                raise ValueError("Payload is not a Telegram update.")
        except (TypeError, ValueError):
            return web.json_response({"error": "invalid update"}, status=400)

        await telegram_application.update_queue.put(update)
        return web.json_response({"status": "accepted"})

    async def telegram_lifecycle(_: web.Application) -> AsyncIterator[None]:
        await telegram_application.initialize()
        if telegram_application.post_init:
            await telegram_application.post_init(telegram_application)
        await telegram_application.start()
        await telegram_application.bot.set_webhook(
            url=webhook_url,
            secret_token=webhook_secret,
            allowed_updates=Update.ALL_TYPES,
        )
        LOGGER.info("Telegram webhook registered at %s", webhook_url)

        try:
            yield
        finally:
            await telegram_application.stop()
            await telegram_application.shutdown()

    app = web.Application()
    app.router.add_get(HEALTH_PATH, health)
    app.router.add_post(WEBHOOK_PATH, telegram_webhook)
    if manage_lifecycle:
        app.cleanup_ctx.append(telegram_lifecycle)
    return app


def run() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )

    token = os.getenv("BOT_TOKEN", "")
    application = create_application(token)
    mode = os.getenv("APP_MODE", "polling").lower()

    if mode == "polling":
        LOGGER.info("Starting Stonksy in polling mode")
        application.run_polling()
        return

    if mode != "webhook":
        raise RuntimeError("APP_MODE must be either 'polling' or 'webhook'.")

    base_url = (
        os.getenv("WEBHOOK_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or ""
    ).rstrip("/")
    if not base_url:
        raise RuntimeError(
            "WEBHOOK_BASE_URL or RENDER_EXTERNAL_URL is required in webhook mode."
        )

    webhook_url = f"{base_url}{WEBHOOK_PATH}"
    webhook_secret = os.getenv("WEBHOOK_SECRET", "")
    port = int(os.getenv("PORT", "10000"))
    web_app = create_web_app(application, webhook_secret, webhook_url)
    LOGGER.info("Starting Stonksy webhook server on port %s", port)
    web.run_app(web_app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    run()
