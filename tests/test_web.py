import asyncio
from types import SimpleNamespace

import pytest
from aiohttp.test_utils import TestClient, TestServer
from telegram import Bot, Update

from main import create_application, create_web_app, normalize_webhook_secret


@pytest.mark.asyncio
async def test_health_endpoint():
    fake_application = SimpleNamespace(
        bot=Bot("123456:TEST_TOKEN"),
        update_queue=asyncio.Queue(),
    )
    app = create_web_app(
        fake_application,
        "secret",
        "https://example.com/telegram/webhook",
        manage_lifecycle=False,
    )

    async with TestClient(TestServer(app)) as client:
        response = await client.get("/health")
        body = await response.json()

    assert response.status == 200
    assert body == {"status": "ok"}


@pytest.mark.asyncio
async def test_webhook_rejects_missing_secret():
    fake_application = SimpleNamespace(
        bot=Bot("123456:TEST_TOKEN"),
        update_queue=asyncio.Queue(),
    )
    app = create_web_app(
        fake_application,
        "secret",
        "https://example.com/telegram/webhook",
        manage_lifecycle=False,
    )

    async with TestClient(TestServer(app)) as client:
        response = await client.post("/telegram/webhook", json={"update_id": 1})

    assert response.status == 403
    assert fake_application.update_queue.empty()


@pytest.mark.asyncio
async def test_webhook_accepts_authenticated_update():
    fake_application = SimpleNamespace(
        bot=Bot("123456:TEST_TOKEN"),
        update_queue=asyncio.Queue(),
    )
    app = create_web_app(
        fake_application,
        "secret",
        "https://example.com/telegram/webhook",
        manage_lifecycle=False,
    )

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/telegram/webhook",
            json={"update_id": 42},
            headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        )

    assert response.status == 200
    update = fake_application.update_queue.get_nowait()
    assert isinstance(update, Update)
    assert update.update_id == 42


@pytest.mark.asyncio
async def test_webhook_rejects_malformed_update():
    fake_application = SimpleNamespace(
        bot=Bot("123456:TEST_TOKEN"),
        update_queue=asyncio.Queue(),
    )
    app = create_web_app(
        fake_application,
        "secret",
        "https://example.com/telegram/webhook",
        manage_lifecycle=False,
    )

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/telegram/webhook",
            data="not json",
            headers={
                "Content-Type": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": "secret",
            },
        )

    assert response.status == 400
    assert fake_application.update_queue.empty()


def test_generated_webhook_secret_is_normalized_for_telegram():
    normalized = normalize_webhook_secret("base64/value+with=padding")

    assert len(normalized) == 64
    assert normalized.isalnum()


def test_create_application_requires_token():
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        create_application("")
