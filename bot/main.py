from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from django.conf import settings

from .handlers import browse, matches, my_reports, start, wizard
from .middlewares import UserMiddleware


def build_dispatcher():
    """Wire the routers together. (A separate function so the tests can use it too.)"""
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.filter(F.chat.type == "private")  # ignore the office group chat
    dp.message.outer_middleware(UserMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())

    # `start` first: /start must work even in the middle of a wizard.
    dp.include_routers(
        start.router, wizard.router, browse.router, my_reports.router, matches.router
    )
    return dp


async def main():
    """Run the bot with long polling. Django is already set up by `manage.py runbot`."""
    await build_dispatcher().start_polling(Bot(token=settings.BOT_TOKEN))
