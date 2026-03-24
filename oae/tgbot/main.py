import asyncio
from aiogram import Dispatcher
from .loader import bot
from tgbot.telegram.handlers import start_router


dp = Dispatcher()
dp.include_router(start_router)


async def start_bot():
    print("Bot started")
    await dp.start_polling(bot)