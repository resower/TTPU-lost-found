import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bot.main import main


class Command(BaseCommand):
    help = "Run the Telegram bot (long polling)."

    def handle(self, *args, **options):
        if not settings.BOT_TOKEN:
            raise CommandError("BOT_TOKEN is empty. Put your bot token in the .env file.")
        asyncio.run(main())
