from django.core.management.base import BaseCommand
import asyncio
from tgbot.main import start_bot

class Command(BaseCommand):
    help = "Run Telegram bot"

    def handle(self, *args, **options):
        asyncio.run(start_bot())