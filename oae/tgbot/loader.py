from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from django.conf import settings
from aiogram.client.session.aiohttp import AiohttpSession

session = AiohttpSession(
    timeout=60
)

bot = Bot(
    token=settings.TELEGRAM_TOKEN,
    session=session,
    default=DefaultBotProperties(parse_mode="HTML")
)